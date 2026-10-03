# it_password_policy

**Status:** open · **Requested by:** Claude Code, 2026-10-02 · **Used in:** room night_shift, `Office/Pinboard/PasswordPolicy` (hard mode: tells players how Mark's password is built, so they can make a wordlist to crack the hash on the USB stick; flavour in standard mode)
**Output:** `game/rooms/night_shift/assets/docs/it_password_policy.png`, portrait A5 ratio, 1024 x 1448 px, opaque.

A corporate IT notice printed on plain office paper, pinned up, slightly curled, one corner a little dog-eared, a faint drawing-pin hole at the top. Clean corporate layout with a small Kestrel Logistics wordmark (a simple stylised bird mark, original). Exact text (hierarchy up to you):

- `KESTREL LOGISTICS - IT`
- `PASSWORD POLICY (rev 3)`
- `All staff passwords must follow this pattern:`
- `1. One word you will remember, starting with a capital letter`
- `2. One symbol:   !   #   $   %   &   *`
- `3. The year you joined Kestrel (4 digits)`
- `Example:  Falcon!2016`
- `Change your password every 12 months. Never write it down.`
- printed at the bottom: `Five failed logins lock your account. IT will never ask for your password.`

The six symbols must be clearly distinguishable at 25 % size (spaced out, large). The example line must read exactly `Falcon!2016`.

## Acceptance
- [ ] PNG at the output path, exact text, legible in the 25 % preview
- [ ] report in `assets/reports/printables/it_password_policy.md`
