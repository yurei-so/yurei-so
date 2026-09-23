# Profile badge generator

`scripts/generate_profile_badges.py` owns only the section of `README.md`
between `profile-badges:start` and `profile-badges:end`. Static badge labels,
colors, logos, order, and future Runtime Roost aggregate keys live in
`profile-badges.json`.

Run it locally with:

```bash
python3 scripts/generate_profile_badges.py
python3 -m unittest discover -s tests -v
python3 scripts/generate_profile_badges.py --check
```

The scheduled/manual `Refresh profile badges` workflow commits only
`README.md` when generated output changes. Its own commit does not retrigger the
workflow because the workflow has no push trigger.

## Future Runtime Roost activation

The adapter is inert by default. Activate it only after a narrow, read-only
public-profile aggregate endpoint exists:

1. Add repository variable `ROOST_PROFILE_STATS_ENABLED` with value `true`.
2. Add repository variable `ROOST_PROFILE_STATS_URL` containing the HTTPS
   endpoint. The endpoint is configuration, not a credential.
3. Add Actions secret `ROOST_PROFILE_STATS_TOKEN` containing the read-only
   bearer credential.

The endpoint response contract is:

```json
{
  "schema": "runtime-roost/public-profile-aggregates/v1",
  "aggregates": {
    "research_experiments_published": 12,
    "active_agents": 3
  }
}
```

Only keys allowlisted in `profile-badges.json` are consumed. Runtime Roost may
supply bounded scalar values, but it cannot supply Markdown, URLs, colors,
labels, logos, or badge ordering. Responses are limited to 64 KiB and invalid
or unavailable responses fall back to the static badge row. The token is sent
only in the HTTPS `Authorization` header and is never included in generated
output or error messages.
