# Advertising Management API v1

Use this module for Unity Acquire apps, campaigns, budgets, bids, targeting, creatives, and creative packs.

## Access and authentication

The organization must have Advertising Management API access enabled by Unity. Create a Unity service account and assign only the roles needed for the task:

- `Advertise API Viewer`
- `Advertise API Apps Editor`
- `Advertise API Campaigns Editor`
- `Advertise API Bids Editor`
- `Advertise API Creative Packs Editor`
- `Advertise API Targeting Editor`
- `Advertise API Admin`

Authenticate with Base64-encoded service-account `keyId:secretKey` Basic credentials or a long-lived service-account bearer token.

## Resource model

```text
Organization
└── App (campaignSetId)
    ├── Campaign (campaignId)
    │   ├── budget
    │   ├── CPI, source, ROAS, retention, and event-optimization bids
    │   ├── targeting
    │   └── assigned creative packs
    ├── creatives
    └── creative packs
```

Use the Organization Core ID. App and campaign IDs are 24-character hexadecimal IDs.

## Mutation policy

- Fetch current state before `PATCH`, `PUT`, or `DELETE`.
- Preview the exact method, relative path, IDs, current value, and JSON body.
- Require explicit confirmation before `--execute`.
- Do not automatically retry a mutation.
- Verify every successful mutation with a GET and compare the requested fields with the returned state.
- Treat app deletion as destructive and unrecoverable; it also removes campaigns, bids, and creative packs.
- Do not use the generic JSON caller for creative binary uploads.

Built-in actions cover app and campaign creation/update, campaign budget changes,
partial CPI/source/retention bid updates, targeting updates, and creative-pack
creation/update/deletion. Use a generic documented path for newer JSON endpoints,
ROAS replacement, event-optimization bids, and creative-pack assignment until a
schema-aware named action is added.

The generic caller accepts only a path relative to:

```text
https://services.api.unity.com/advertise/v1/organizations/{organizationId}/
```

It rejects absolute URLs, embedded query strings, traversal, and alternate hosts.

For a generic list mutation that uses null values to delete entries, pass `--verify-keys` with the documented identity fields so the verifier can prove that each deleted entry is absent. Built-in bid actions provide their identity fields automatically.

Official documentation: https://services.docs.unity.com/advertise/v1/
