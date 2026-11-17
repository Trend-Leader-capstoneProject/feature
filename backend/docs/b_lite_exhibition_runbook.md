# B-Lite exhibition — E0 read-only preflight

Status: **E0 ONLY / REVIEW_ONLY / NOT PUBLISHED / G5-G6 HOLD**. This command never connects to a DB, publishes content, authenticates reviewers, or validates a real approval source. It does not replace the existing G5 P1 HOLD gate, isolated Daily CLI, Phase 4 FROZEN work, or B-3/L-2.

## Windows usage

From a project checkout with the backend Python environment activated, supply a UTF-8 JSON manifest path:

```powershell
cd backend
python -m scripts.b_lite_exhibition_once --input "C:\path\to\review-manifest.json"
```

Or pass/drop the path onto `backend\scripts\run_b_lite_exhibition.bat`. The `.bat` simply invokes the same **read-only** Python CLI; there is **no execute/publish switch**. `REVIEW_ONLY` returns exit code 0, `BLOCKED` returns 1, invalid CLI options return 2. Never put credentials in manifests or the repository.

## Candidate manifest (synthetic-only example)

```json
{
  "schema": "B_LITE_EXHIBITION_REVIEW_V1",
  "profile_id": "MVP_A_EXHIBITION_20261118_19",
  "approval_scope": "REVIEW_ONLY",
  "g6_status": "HOLD",
  "batch_id": "EXAMPLE-REVIEW-ONLY",
  "records": [
    {
      "kind": "SYNTHETIC_DEMO",
      "title": "【DEMO】 가상 시연 주제",
      "summary": "가상의 시연 데이터입니다. 실제 검색·수집 결과가 아닙니다.",
      "thumbnail_url": null,
      "google_rss_derived": false,
      "parent_code": "GAME",
      "child_name": "기타",
      "source_url": null,
      "source_title": null
    }
  ]
}
```

`REVIEWED_REAL` additionally requires `review_evidence_id`, syntactically valid `content_ref` (`sha256:` plus 64 lowercase hexadecimal digits), `source_review=URL_TITLE_KEY_CLAIMS_VERIFIED`, an external HTTPS `source_url`, `source_title_origin=NONE` plus `source_title=null` and `source_label_evidence_id=null`; or `EDITORIAL_LABEL` with a team-authored `source_title` (1–80 characters) and nonempty `source_label_evidence_id`. Those fields are **untrusted declarations**. This tool does not validate evidence authenticity, source content, link reachability, content hash match, actual category existence, Google RSS provenance, runtime GRANT, or G6 approval. Such checks belong to a separate, approved next phase.

Input: 1–36 records and <=1 MB; six known parent category codes; duplicate JSON keys, duplicate title or repeated real source URLs are rejected. The output is either `BLOCKED` with a reason, or `REVIEW_ONLY`, never publication authorization. The JSON file is read only and no report file is written.

## Next phase — not included

Do not run an operational `INSERT`, `HIDDEN` pre-registration, migration, permission change, or APK publishing based on this result. A dedicated, separately approved one-shot Writer would require trusted G4/G6 evidence validation, actual target DB identity/GRANT validation, durable Journal, batch atomic transaction, withdrawal/revoke behavior, isolated tests, and independent B-3/L-2/production approvals. G5/G6 remain HOLD until independently evidenced.

Run the isolated tests from `backend` with `python -m pytest tests/core/test_b_lite_exhibition_once.py -q`. PowerShell paths and commands in this document have not been validated on the user's actual Windows machine.
