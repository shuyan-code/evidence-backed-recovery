# Market research and positioning

Research date: 2026-09-27. Scope: public web and GitHub search for Agent Skills related to customer sentiment, complaint handling, concessions, and service recovery. This is a documented comparison of the surveyed set, not proof that no similar project exists anywhere.

## Demand signal

Zendesk's [2026 CX Trends announcement](https://www.zendesk.com/newsroom/press-releases/contextual-intelligence-becomes-the-new-standard-for-exceptional-customer-experience-in-2026/) reports that 85% of surveyed CX leaders say one unresolved issue can be enough to lose a customer. The figure is a vendor survey result, not a measured effect of this skill. [Service recovery research](https://doi.org/10.5465/amp.2014.0143) connects organizational investment in recovery with customer and organizational outcomes. A [2025 compensation study](https://doi.org/10.1007/s11628-025-00597-z) found that expected monetary compensation changes with failure severity and type, supporting a contextual policy gate instead of a single generic refund rule.

These sources support a real operational problem. They do not establish willingness to pay for this particular implementation. The commercial hypothesis must be tested with support teams using real, privacy-safe cases.

## Surveyed alternatives

| Project | Observed capability | Gap this project targets |
| --- | --- | --- |
| [Composio support-skills](https://github.com/composio-community/support-skills) | Sentiment check, angry-customer playbook, ticket triage, and CRM-connected workflows | A small offline workflow that links evidence, concession policy, approval reference, and observed outcome in one portable skill |
| [murphye/agent-skills-customer-service](https://github.com/murphye/agent-skills-customer-service) | Policy-driven service workflow, refund escalation, and scenario tests | A minimal, vendor-independent outcome ledger with explicit known/unknown retention denominators |
| [Skill Me refund and de-escalation](https://github.com/SkillMedev/skills) | De-escalation and a refund matrix using LTV and chargeback risk | Evidence IDs, deterministic policy ceilings, and a post-follow-up outcome record without inferring churn probability |
| [consumer-dispute-agent-skill](https://github.com/JerryNee/consumer-dispute-agent-skill) | Consumer-side dispute case packs and evidence trails | Merchant-side B2B recovery governance and descriptive operating metrics |

The market is crowded. The differentiator is the combined operating loop and its conservative boundaries, not a novel sentiment model or a claim to own service recovery. This project intentionally avoids LTV-based automatic eligibility, emotional diagnosis, and automated financial action.

## Buyer, workflow, and value test

**Likely buyer:** support operations or customer-success leadership at a B2B SaaS organization with written concession limits and ticket/incident records.

**Workflow:** complaint intake → evidence check → proposed remedy → policy/approval gate → human communication and action → follow-up → outcome ledger → review of resolution, repeat contact, known retention, and cost.

**Pilot acceptance criteria:** in a prospective team-selected sample, measure the share of cases with linked evidence, verified authorization before financial action, completed follow-up, repeat complaints, and concession spend. Compare with the team's prior process and review cases qualitatively. Do not claim retention uplift without a credible comparison design and sufficient observation time.

**Open-source business path:** publish the MIT skill and CLI; offer paid implementation, verified connector development, policy migration, and managed reporting if customers request them. No paid tier or customer demand is represented as already validated.

## Research limitations

Search indexing is incomplete and changes over time. The comparison covers the linked projects found in this search, not every private tool, vendor feature, or GitHub repository. Vendor survey figures can reflect survey design and respondent composition. The cited research supports service recovery as a business problem but does not validate this code or its economics.
