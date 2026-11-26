# Harness introduction: primary-source review

Review date: 2026-11-23. Scope: the six references introduced with the
harness-framed introduction in `paper\skillachievability.tex`.
The earlier quantitative introduction paragraph is commented out and is not
part of the rendered paper. Its values must not be restored without the
qualifications below. No experimental measurements come from this review.

## Survey (`harnesssurvey`)

The inspected first-party project copy of *Agent Harness Engineering: A Survey*
lists 15 authors: Junjie Li, Xi Xiao, Yunbei Zhang, Chen Liu, Lin Zhao,
Xiaoying Liao, Yingrui Ji, Janet Wang, Yingqiang Ge, Weijie Xu, Xi Fang,
Xiang Xu, Tianchen Zhao, Youngeun Kim, and Tianyang Wang.
The previous manuscript's 20-author list does not match that version.

- [Pinned project PDF](https://huggingface.co/datasets/ChenLiu1996/Agent-Harness-Engineering/resolve/cbdb25e65f27874077a906b95b5746f0642e9551/Agent_Harness_Engineering_Survey.pdf), title page and Section 1.
- [Project README identifying its survey PDF](https://huggingface.co/datasets/ChenLiu1996/Agent-Harness-Engineering/raw/cbdb25e65f27874077a906b95b5746f0642e9551/README.md).
- Inspected PDF SHA256: `ab233178b88cbc8e3a3ad5b5cbebfe5c44a4437622526739a9b4e324d8281a37`.

Section 1 supports describing harness infrastructure as context, tool
interfaces, state, verification, and permissions surrounding an agent.
It does not establish that the harness always matters more than the model.
The venue page and its metadata endpoint blocked direct access; different
observed versions have different author lists. The revision adopts the pinned
project copy explicitly, not an inferred author list for another version.
PDF generation metadata is not evidence of an original publication date.

## HarnessFix (`harnessfix`)

Mengzhuo Chen, Junjie Wang, Zhe Liu, Yawen Wang, Haiming Zheng, and Qing Wang.
*From Failed Trajectories to Reliable LLM Agents: Diagnosing and Repairing
Harness Flaws*. arXiv:2606.06324, 2026.

- [Version 2 record](https://arxiv.org/abs/2606.06324v2).
- [Primary text](https://arxiv.org/html/2606.06324v2), Sections I, II-A, IV-B, and V-A, Table III.

Section II-A distinguishes repair of prompts, tool specifications, and
orchestration from changing model parameters. Execution traces support
diagnosis and repair, not a claim that execution is the only possible way
to discover structural failures.

Table III reports GPT-5 mini gains of 18.4 percentage points on GAIA
(43.3% to 61.7%) and 6.3 points on AppWorld (36.7% to 43.0%). The four
GPT-5 mini rows support the 6.3--18.4-point range. Across all five models,
the range is 5.9--18.4 points: AppWorld with DeepSeek V3.2 changes from
56.3% to 62.2%. The abstract's narrower range must not be attributed to
all model configurations. These are percentage-point differences.

## Agent Skills (`agentskills`)

Agent Skills. *Specification*. Pinned commit
`83021e2be457a9b6679148719c1f6074f0ad975e`, accessed 2026-11-23.

- [Specification](https://github.com/agentskills/agentskills/blob/83021e2be457a9b6679148719c1f6074f0ad975e/docs/specification.mdx), directory structure, lines 6--32.
- [Overview](https://github.com/agentskills/agentskills/blob/83021e2be457a9b6679148719c1f6074f0ad975e/docs/home.mdx), overview and progressive disclosure, lines 10--14 and 33--43.

A directory containing `SKILL.md` is required. Scripts, references, and
assets are optional. Discovery and on-demand loading are supported by the
overview. Replace "instructions and tooling" with "instructions and optional
scripts or other resources". A 2025 publication year was not established;
use the pinned version and access date instead.

## ADAS (`adas`)

Shengran Hu, Cong Lu, and Jeff Clune. *Automated Design of Agentic Systems*.
ICLR 2025, pp. 21344--21377.

- [Official proceedings record](https://proceedings.iclr.cc/paper_files/paper/2025/hash/36b7acf6f6010652b3f2a433774a66fe-Abstract-Conference.html).

The abstract describes code-defined agentic systems and a meta-agent that
designs agents, including prompts, tool use, and workflows. It supports the
general introduction. The existing bibliographic entry is correct; no
quantitative ADAS claim is made in the reviewed passage.

## AFlow (`aflow`)

Jiayi Zhang, Jinyu Xiang, Zhaoyang Yu, Fengwei Teng, XiongHui Chen, Jiaqi Chen,
Mingchen Zhuge, Xin Cheng, Sirui Hong, Jinlin Wang, Bingnan Zheng, Bang Liu,
Yuyu Luo, and Chenglin Wu. *AFlow: Automating Agentic Workflow Generation*.
ICLR 2025, pp. 34040--34077.

- [Official proceedings record](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5492ecbce4439401798dcd2c90be94cd-Abstract-Conference.html).

The abstract describes detailed instructions, operational sequences, and
search over code-represented workflows. It supports the general introduction.
The existing first-ten-authors-plus-et-al. entry is correct; no quantitative
AFlow claim is made in the reviewed passage.

## Multi-agent failures (`cemri`)

Mert Cemri, Melissa Z. Pan, Shuyi Yang, Lakshya A. Agrawal, Bhavya Chopra,
Rishabh Tiwari, Kurt Keutzer, Aditya Parameswaran, Dan Klein,
Kannan Ramchandran, Matei A. Zaharia, Joseph E. Gonzalez, and Ion Stoica.
*Why Do Multi-Agent LLM Systems Fail?* NeurIPS 2025, Datasets and Benchmarks
Track; arXiv:2503.13657.

- [Official proceedings record](https://proceedings.neurips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html).
- [Version 3 primary text](https://arxiv.org/html/2503.13657v3), Section 1, Appendix B, and Appendix H.2, Table 5.

The 41--86.7% failure range is reported for seven studied open-source
multi-agent systems under their evaluated configurations, not as a population
failure estimate. Table 5 reports ChatDev ProgramDev-v0 accuracy on 32 tasks:
25.0% baseline, 34.4% improved prompt, and 40.6% new topology. Thus the
15.6-point difference is associated with the topology intervention, which
uses a cyclic review process and review-dependent termination with a cutoff.
The paper's narrative attributes this differently. The table does not isolate
the effect of simply adding one verification instruction. Keep the active
qualitative statement; do not restore the stronger causal attribution.

## Integration boundary

The revision corrects the skill definition, qualifies trace-based diagnosis,
adopts the pinned survey's author list, replaces the specification's unverified
year with an access date, and adds the verified NeurIPS venue for Cemri et al.
The commented historical paragraph remains unchanged as history. No primary
source above establishes accuracy, net savings, or deployment safety for SkillC.
