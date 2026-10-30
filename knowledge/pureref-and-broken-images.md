# Reference images the API refuses, and PureRef boards

**Seen on:** an earlier project, Stage 0, 2026-10-29 · **Modes:** all · **Routes:** all

**Symptom:** Reading reference images failed with "Could not process image" or "media removed — rejected by API", and an agent sent to describe them failed the same way. The images came from a PureRef 2 `.pur` file.
**Cause:** The images were corrupt. A PureRef 2 `.pur` stores each image's first block or so as a normal JPEG or PNG, and the rest in a form with no readable structure. Scanning the file for JPEG and PNG signatures recovered 13 of about 45 images, and every one was scrambled below its first strip. The API refuses images it can't decode. Clean images of any size, up to 1920×1080 tested, loaded fine.
**Fix:**
1. Don't extract from a `.pur`. Ask the user to export its images from PureRef, one subfolder per group, so the group names carry over.
2. Run `.claude/skills/input-review/scripts/prep_refs.py` on every reference folder before any agent views it. It rejects files that won't decode, writes clean copies with a 1568 px long edge, and makes labelled contact sheets of 9.
3. Review from the sheets first. One sheet costs about as much as one image, so a large batch needs far fewer tokens.
**Test:** `prep_refs.py --selftest` (a truncated file must be rejected). The script can't detect a file that decodes but shows scrambled pixels, so check the first contact sheet by eye.
