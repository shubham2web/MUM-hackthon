# ATLAS Development To-Do List

## Core Features
- [x] **Multi-Agent Structured Debate**: Integrated with Groq and HuggingFace APIs.
- [x] **Evidence Grounder & Diversification**: Successfully gathers evidence with provenance metadata.
- [x] **Bias Auditor System**: Flags bias and gaps in evidence.
- [ ] **Role Reversal & Convergence Rounds**: Implement functionality to reverse agent roles and log alternate arguments.
- [x] **Moderator & Transparent Synthesis**: Synthesis includes provenance and bias summaries.
- [x] **Audit Log & User Interface**: Functional UI with transcript visualization and bias dashboard.

---

## Technical Requirements
- [x] **Data & Storage**: Evidence and logs are stored in the database.
- [ ] **Auth & Security**: Implement API key authentication and RBAC for user roles.
- [ ] **Analytics & Metrics**: Track diversity scores, contradiction ratios, and audit coverage.

---

## MVP Scope
- [x] **Model Interface Layer**: Integrated with Groq and HuggingFace.
- [x] **Core Agent Manager**: Functional; orchestrates AI agents and evidence gathering.
- [ ] **Role Prompt Library**: Define prompts for 4–6 roles with distinct personas or perspectives.
- [x] **Evidence Grounder Prototype**: Successfully implemented.
- [x] **Bias Auditor**: Functional; flags bias and gaps in evidence.
- [ ] **Role Reversal Engine**: Implement functionality for role reversal.
- [x] **Moderator & Synthesis Output**: Functional; synthesis includes provenance and bias summaries.
- [x] **UI with Transcript & Bias Dashboard**: Functional; logs confirm user interaction with endpoints.

---

## Next Steps
1. **Implement Role Reversal & Convergence Rounds**:
   - Add functionality to reverse agent roles and log alternate arguments.

2. **Add Analytics & Metrics**:
   - Track diversity scores, contradiction ratios, and audit coverage.

3. **Enhance Security**:
   - Implement API key authentication and RBAC for user roles.

4. **Expand Role Prompt Library**:
   - Define prompts for distinct personas or perspectives.

---