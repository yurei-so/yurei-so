# Profile badge generator

`scripts/generate_profile_badges.py` owns only the section of `README.md`
between `profile-badges:start` and `profile-badges:end`. Static badge labels,
colors, logos, order, and optional dynamic badge keys live in
`profile-badges.json`.

Run it locally with:

```bash
python3 scripts/generate_profile_badges.py
python3 -m unittest discover -s tests -v
python3 scripts/generate_profile_badges.py --check
```

The manual `Refresh profile badges` workflow commits only `README.md` when
generated output changes. Its own commit does not retrigger the workflow
because the workflow has no push trigger.

An optional trusted publisher may supply a JSON object through the workflow's
`values` input. Only keys already declared under `dynamic` in
`profile-badges.json` are consumed. Values are bounded scalars; the publisher
cannot supply Markdown, URLs, colors, labels, logos, or badge ordering. With no
input, generation produces the static badge row.
