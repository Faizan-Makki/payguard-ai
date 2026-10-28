# PayPal AI Hackathon submission checklist

Checked against the [official rules](https://paypalaihackathon.devpost.com/rules) and [project overview](https://paypalaihackathon.devpost.com/) on 2026-10-27. The rules call for a meaningful PayPal Sandbox integration and meaningful AI use; the submission needs a functional demo, text description, public code repository with open-source license, tools used, and a public YouTube demo video under three minutes.

## Build and evidence

- [x] Working local demo in synthetic mode, with source labeling and setup instructions.
- [x] Explainable rule-based findings and an end-to-end merchant review workflow.
- [x] Configured AI call path is implemented; deterministic fallback works without credentials.
- [x] PayPal Sandbox OAuth and Transaction Search path is implemented and mock-tested.
- [ ] Run the PayPal Settings connection probe with your Sandbox app credentials.
- [ ] Verify a real reporting response and, separately, whether relevant test transactions are returned. PayPal documents up to a three-hour reporting delay.
- [ ] Run a provider-backed AI explanation with an authorized key and confirm the explanation matches the displayed finding.
- [ ] Record a public YouTube demo showing the functioning project, under three minutes.

## Submission materials and publication

- [ ] Write and submit the Devpost project description, including the merchant problem, workflow, limitations, and the actual integration evidence.
- [ ] Publish the project source to a public GitHub, GitLab, or Bitbucket repository; include all source, assets, and run instructions.
- [x] MIT `LICENSE` file is present; project owner confirmed keeping MIT on 2026-10-27.
- [ ] In the submission, identify the tools actually used. Expected entries include Streamlit, PayPal Transaction Search API, and the AI provider/model only if live use is verified.
- [ ] Add the public repository URL and public video URL to the submission form.
- [ ] Ensure the demo video has no unauthorized third-party trademarks or copyrighted material.

## Submission rules

- [x] Official deadline verified: Nov 12, 2026 at 12:00 PM Pacific.
- [ ] Register/join through Devpost and submit all required form fields before the deadline.
- [ ] Confirm eligibility and team representative requirements for the entrant.

Do not describe Sandbox or AI integrations as live-verified until the manual checks above succeed. The current local tests use mocked API responses and do not prove access to a real PayPal or AI account.
