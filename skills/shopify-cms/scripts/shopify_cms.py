#!/usr/bin/env python3
"""Shopify blog publishing using the Frevana App's GraphQL contract."""
import json
import re
import sys
from urllib.parse import quote, urlencode

from cms_common import Config, Failure, cli_main, http, parser_for, read_json, require, text_field

FIELDS = ("store_domain", "client_id", "client_secret", "blog_id", "api_version", "default_author")
DEFAULTS = {"api_version": "2026-04"}
SETUP_GUIDE = "https://frevana.gitbook.io/frevana-docs/cms-integrations/shopify-cms-integration"
ARTICLE_FIELDS = "id title handle body summary tags isPublished blog { id handle }"


def domain(value):
    value = re.sub(r"^https://", "", value.strip()).rstrip("/").lower()
    require(bool(re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", value)),
            "store_domain must be the canonical STORE.myshopify.com host (optional https://)")
    return value


def gid(kind, value):
    require(bool(re.fullmatch(r"[1-9][0-9]*|gid://shopify/" + kind + r"/[1-9][0-9]*", value or "")),
            f"Expected a numeric {kind} ID or gid://shopify/{kind}/ID")
    return value if value.startswith("gid:") else f"gid://shopify/{kind}/{value}"


class Shopify:
    def __init__(self, config):
        config.need("store_domain", "client_id", "client_secret", "api_version")
        self.config, self.values = config, config.values
        self.host = domain(self.values["store_domain"])
        require(bool(re.fullmatch(r"20[0-9]{2}-(01|04|07|10)", self.values["api_version"])),
                "api_version must be a stable YYYY-01/04/07/10 version")
        self.token = None

    def query(self, query, variables=None):
        if self.token is None:
            response = http("POST", f"https://{self.host}/admin/oauth/access_token",
                            {"Content-Type": "application/x-www-form-urlencoded"},
                            urlencode({"client_id": self.values["client_id"],
                                       "client_secret": self.values["client_secret"],
                                       "grant_type": "client_credentials"}), form=True)
            self.token = response.get("access_token")
            require(isinstance(self.token, str) and self.token, "Token exchange returned no access_token")
            # Retain only in memory and include it in output redaction.
            self.config.values["access_token"] = self.token
            self.config.secrets = (*self.config.secrets, "access_token")
        response = http("POST", f"https://{self.host}/admin/api/{self.values['api_version']}/graphql.json",
                        {"Content-Type": "application/json", "X-Shopify-Access-Token": self.token},
                        {"query": query, "variables": variables or {}})
        if response.get("errors"):
            raise Failure("Shopify GraphQL errors; reconcile before repeating a mutation", response=response)
        require(isinstance(response.get("data"), dict), "Shopify returned no GraphQL data")
        return response["data"]

    def blog(self, value):
        data = self.query("query($id: ID!) { node(id: $id) { ... on Blog { id title handle } } }",
                          {"id": gid("Blog", value)})
        require(isinstance(data.get("node"), dict) and data["node"].get("id") == gid("Blog", value),
                "Selected Shopify blog not found")
        return data["node"]

    def article(self, value):
        data = self.query("query($id: ID!) { article(id: $id) { " + ARTICLE_FIELDS + " } }",
                          {"id": gid("Article", value)})
        require(isinstance(data.get("article"), dict) and data["article"].get("id") == gid("Article", value),
                "Shopify article not found")
        return data["article"]


def article_input(args, config):
    require(args.data_file, "--data-file is required")
    data = read_json(args.data_file)
    require(not set(data) - {"title", "bodyHtml", "summary", "author", "tags"}, "Unknown content fields")
    for key in ("title", "bodyHtml"):
        text_field(data, key, required=True)
    for key in ("summary", "author"):
        text_field(data, key)
    if "tags" in data:
        require(isinstance(data["tags"], list) and all(isinstance(v, str) for v in data["tags"]),
                "tags must be an array of strings")
    config.need("store_domain", "blog_id")
    payload = {"blogId": gid("Blog", config.values["blog_id"]), "title": data["title"],
               "body": data["bodyHtml"], "isPublished": True}
    for key in ("summary", "tags"):
        if key in data:
            payload[key] = data[key]
    author = data.get("author", config.values["default_author"])
    if author:
        payload["author"] = {"name": author}
    elif args.action == "create":
        payload["author"] = {"name": "Frevana"}
    return payload


def run(args, config):
    if args.action == "configure":
        return config.configure(("store_domain", "client_id", "client_secret"),
                                lambda values: domain(values["store_domain"]))
    if args.action in ("create", "update"):
        payload = article_input(args, config)
        variables = {"article": payload}
        if args.action == "update":
            variables["id"] = gid("Article", args.id)
        if not args.execute:
            return {"dryRun": True, "store": domain(config.values["store_domain"]),
                    "operation": args.action, "variables": variables}
    api = Shopify(config)
    if args.action == "status":
        shop = api.query("query { shop { name myshopifyDomain } }")
        require(isinstance(shop.get("shop"), dict), "Shop query returned no shop")
        if config.values["blog_id"]:
            shop["blog"] = api.blog(config.values["blog_id"])
        return shop
    if args.action == "blogs":
        return api.query("query($after: String) { blogs(first: 250, after: $after) { nodes { id title handle } "
                         "pageInfo { hasNextPage endCursor } } }", {"after": args.after})
    if args.action == "get":
        return api.article(args.id)
    if args.action == "articles":
        config.need("blog_id")
        require(1 <= args.limit <= 250, "--limit must be 1..250")
        return api.query("query($id: ID!, $first: Int!, $after: String) { blog(id: $id) { id "
                         "articles(first: $first, after: $after) { nodes { id title handle isPublished } "
                         "pageInfo { hasNextPage endCursor } } } }",
                         {"id": gid("Blog", config.values["blog_id"]), "first": args.limit, "after": args.after})
    blog = api.blog(config.values["blog_id"])
    if args.action == "update":
        current = api.article(args.id)
        require(current.get("blog", {}).get("id") == payload["blogId"],
                "Article belongs to a different blog; refusing to move it")
    operation = "articleCreate" if args.action == "create" else "articleUpdate"
    declaration = "$article: ArticleCreateInput!" if args.action == "create" else "$id: ID!, $article: ArticleUpdateInput!"
    call = "article: $article" if args.action == "create" else "id: $id, article: $article"
    response = api.query("mutation(" + declaration + ") { " + operation + "(" + call +
                         ") { article { " + ARTICLE_FIELDS + " } userErrors { field message code } } }", variables)
    result = response.get(operation)
    if not isinstance(result, dict):
        raise Failure("Mutation returned no result; reconcile before retrying", response=response)
    if result.get("userErrors"):
        raise Failure("Shopify mutation rejected", response=response)
    article = result.get("article")
    if not isinstance(article, dict) or not isinstance(article.get("id"), str) or not article["id"]:
        raise Failure("Mutation returned no article ID; reconcile before retrying", response=response)
    if args.action == "update" and article["id"] != variables["id"]:
        raise Failure("Mutation returned a different article ID; reconcile before retrying", response=response)
    warnings = []
    verified = None
    try:
        verified = api.article(article["id"])
    except Failure as exc:
        warnings.append({"verificationError": str(exc), **exc.details})
    observed = verified or article
    published = observed.get("isPublished") is True
    if observed.get("body") != payload["body"]:
        warnings.append("Stored body differs from submitted body; no rollback was performed")
    candidate = None
    if blog.get("handle") and observed.get("handle"):
        candidate = f"https://{api.host}/blogs/{quote(blog['handle'], safe='')}/{quote(observed['handle'], safe='')}"
    return {"remoteObjectId": article["id"], "status": "published" if published else "unverified",
            "remoteUrlCandidate": candidate, "response": response, "verified": verified, "warnings": warnings}


def main():
    parser = parser_for(__doc__, ("status", "blogs", "articles", "get", "create", "update"), FIELDS)
    parser.add_argument("--after", help="Verbatim cursor for the next explicitly requested page")
    args = parser.parse_args()
    try:
        config = Config(args, "SHOPIFY", FIELDS, DEFAULTS, ("client_secret",), setup_guide=SETUP_GUIDE)
    except Failure as exc:
        print(json.dumps({"error": str(exc), **exc.details}))
        return 1
    return cli_main(run, args, config)


if __name__ == "__main__":
    sys.exit(main())
