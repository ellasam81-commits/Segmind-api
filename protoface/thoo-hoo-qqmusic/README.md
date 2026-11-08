# T Hoo Hoo QQ Music tutorial — independent workflow

Workflow: `.github/workflows/thoo-hoo-qqmusic.yml`.
Code: `protoface/thoo-hoo-qqmusic/`.
Uses the existing repository secret `PROTOFACE_API_KEY`; never prints the secret.

This project does not import, edit, trigger or reuse Thirteen Doors scripts, inputs, checkpoints, artifacts, or concurrency groups. It only shares the provider credential.

## Scope
60-second Chinese tutorial: 5 parts, 12 seconds each.
Yellow T Hoo Hoo mascot; chibi Tan Jianci; author credit 林爱丽.
Entry: open QQ Music → search 由你榜 → enter it → internal search 檀健次 → Trouble In My DMs → 支持 → TANGENT.
November 10 evening is the supplied group arrangement, not a verified platform event.
Purchase-to-points ratio from group chat remains unverified; do not promise a reward or automatic song recommendation.

## Manual operation
Open Actions → T Hoo Hoo - QQ Music tutorial (Protoface).
Default check_connection makes no paid submission.
inspect_model saves live input schema/pricing without generation.
generate_part requires a reviewed prompt, a HTTPS reference image, a positive max_credits and confirm_spend=true. It submits only the selected part. It validates the 12-second request against the current provider schema and stops if unsupported.
No automatic push, pull request or scheduled trigger.
No five-part batch, retries that create new runs, or automatic final assembly.
Re-run the SAME GitHub run to resume using its checkpoint and idempotency key.
Inputs and artifacts in this public repository can be visible publicly; use only intended tutorial material.
