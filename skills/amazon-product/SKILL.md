---
name: amazon-product
description: Fetch Amazon product details by ASIN through Frevana's `POST /service/serpapi/amazon-product` endpoint. Use whenever the user gives an Amazon ASIN and wants listing details, product attributes, delivery-aware info, or a quick product lookup from Amazon data.
---

# Amazon Product

Retrieve Amazon product details by calling Frevana's `POST https://ai-factory.frevana.com/service/serpapi/amazon-product`.

## Purpose

This skill is for **backend Amazon product lookup**.

Inputs:

- `asin`
- optional `amazon_domain`
- optional `gl`
- optional `hl`
- optional `customer_zipcode`
- optional `force_refresh`

Output:

- validated response JSON returned by the Amazon product endpoint

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the API payload unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `asin`
- optional `amazon_domain`, `gl`, `hl`, `customer_zipcode`, `force_refresh`
- `FREVANA_TOKEN` in the environment, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `asin`.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Return the validated response JSON, or summarize the fields the user actually cares about if they do not need the full payload.
7. When useful, also save the JSON to a file.

## Commands

### Basic product lookup

```bash
bash <skill-path>/scripts/fetch_product.sh \
  --asin B0BDJ49KVD
```

### Delivery-aware lookup

```bash
bash <skill-path>/scripts/fetch_product.sh \
  --asin B0BDJ49KVD \
  --customer-zipcode 10001
```

### Full request with explicit options

```bash
bash <skill-path>/scripts/fetch_product.sh \
  --asin B0BDJ49KVD \
  --amazon-domain amazon.com \
  --gl US \
  --hl en \
  --customer-zipcode 10001 \
  --force-refresh false \
  --output ./out/amazon-product-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/fetch_product.sh \
  --asin B0BDJ49KVD \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape:

```json
{
  "asin": "B0BDJ49KVD",
  "amazon_domain": "amazon.com",
  "gl": "US",
  "hl": "en",
  "customer_zipcode": "10001",
  "force_refresh": false
}
```

Default values when not provided:

- `amazon_domain`: `amazon.com`
- `gl`: `US`
- `hl`: `en`
- `force_refresh`: `false`

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- With `--output`: the same JSON is also written to the specified file path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--asin`
- Ask the user for the ASIN if they only provide a product name or Amazon URL
- Use `--customer-zipcode` when delivery availability or localized offer details matter
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the key fields the user actually cares about instead of dumping raw JSON unless they ask for the full payload

## Example Prompts

### 中文

- "查一下 ASIN B0BDJ49KVD 的商品详情"
- "帮我查 ASIN B0BDJ49KVD，收货邮编 10001"
- "调用 Amazon product API 并把原始 JSON 保存到文件"

### English

- "Fetch Amazon product details for ASIN B0BDJ49KVD"
- "Check ASIN B0BDJ49KVD with customer ZIP 10001"
- "Call the Amazon product endpoint and save the raw JSON to a file"
