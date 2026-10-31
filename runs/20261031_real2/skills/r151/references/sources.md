# Evidence Source Registry

Tiered domains for WebSearch `allowed_domains` parameter and Tavily `include_domains`.

## Tier 1 -- Primary Research & Systematic Reviews

Highest evidence weight. Peer-reviewed, systematic.

### Databases & Aggregators
| Domain | Description |
|--------|-------------|
| `[host-1]` | PubMed + PubMed Central (full-text) |
| `[host-2]` | Gold standard systematic reviews |
| `[host-3]` | WHO guidelines and position papers |
| `[host-4]` | Clinical trial registry |
| `[host-5]` | 41M+ life science publications, free API |
| `[host-6]` | 300K+ systematic reviews aggregated |
| `[host-7]` | Health sciences preprints (flag as preprint) |
| `[host-8]` | Biology preprints (flag as preprint) |

### WebSearch Domain List (copy-paste for Tier 1)
```
[host-1], [host-2], [host-3], [host-4], [host-5], [host-6]
```

## Tier 2 -- Clinical & Institutional

High evidence weight. Expert institutions, clinical guidelines.

### General Medical
| Domain | Description |
|--------|-------------|
| `[host-9]` | Evidence-based patient information |
| `[host-10]` | Johns Hopkins clinical guidance |
| `[host-11]` | Cleveland Clinic health library |
| `[host-12]` | Harvard Health Publishing |
| `[host-13]` | NIH consumer health information |
| `[host-14]` | National Heart, Lung, Blood Institute |
| `[host-15]` | CDC guidelines and MMWR |
| `[host-16]` | NIH (general) |
| `[host-17]` | UK clinical guidelines (NICE CKS) |

### Condition-Specific Organizations
| Domain | Description | Topics |
|--------|-------------|--------|
| `[host-18]` | American Heart Association | Cardiovascular |
| `[host-19]` | American Cancer Society | Oncology |
| `[host-20]` | NCI (National Cancer Institute) | Oncology |
| `[host-21]` | CancerCare | Oncology support |
| `[host-22]` | American Diabetes Association | Diabetes |
| `[host-23]` | NIH Diabetes Education Program | Diabetes |
| `[host-24]` | Joslin Diabetes Center | Diabetes |
| `[host-25]` | Alzheimer's Association | Neurology |
| `[host-26]` | Alzheimer's Information | Neurology |
| `[host-27]` | Congenital Heart Info Network | Cardiology |
| `[host-28]` | National Institute of Mental Health | Mental health |

### Regulatory
| Domain | Description |
|--------|-------------|
| `[host-29]` | US FDA (drug safety, approvals) |
| `[host-30]` | European Medicines Agency |
| `[host-31]` | openFDA API (adverse events, labels) |

### WebSearch Domain List (copy-paste for Tier 2)
```
[host-9], [host-10], [host-11], [host-12], [host-13], [host-14], [host-15], [host-16], [host-17], [host-18], [host-19], [host-20], [host-22], [host-25], [host-29], [host-30], [host-28]
```

## Tier 3 -- Expert Analysis & Evidence Synthesis

Medium weight. Curated expert analysis, evidence-based summaries.

| Domain | Description | Best For |
|--------|-------------|----------|
| `[host-32]` | Evidence-based supplement/nutrition analysis | Supplements, nutrition |
| `[host-33]` | STAT News - medical/pharma journalism | Drug development, policy |
| `[host-34]` | Health News Review - media watchdog | Claim verification |
| `[host-35]` | Scientists fact-check health claims | Viral claim debunking |
| `[host-36]` | Independent supplement testing | Supplement quality |
| `[host-37]` | Dr. Greger's evidence reviews | Plant-based nutrition |
| `[host-38]` | American College of Sports Medicine | Exercise science |
| `[host-39]` | National Strength & Conditioning | Training protocols |
| `[host-40]` | National Sleep Foundation | Sleep science |
| `[host-41]` | National Academy of Sports Medicine | Exercise science |

### AI-Powered Research (use as supplementary)
| Domain | Description |
|--------|-------------|
| `[host-42]` | AI consensus extraction from papers |
| `[host-43]` | Academic search (broad) |

### WebSearch Domain List (copy-paste for Tier 3)
```
[host-32], [host-33], [host-34], [host-35], [host-38], [host-39], [host-40], [host-42]
```

## Tier 4 -- Quality Journalism

Lowest evidence weight. Use for context, framing, public discourse. Never cite as primary evidence.

| Domain | Description |
|--------|-------------|
| `[host-44]` | The Atlantic |
| `[host-45]` | New York Times |
| `[host-46]` | NPR |
| `[host-47]` | The Guardian |
| `[host-48]` | FiveThirtyEight (data journalism) |
| `[host-49]` | Mosaic Science |
| `[host-50]` | Wired (science/tech health) |
| `[host-51]` | Vox (explainers) |

### WebSearch Domain List (copy-paste for Tier 4)
```
[host-44], [host-45], [host-46], [host-47], [host-48]
```

## Topic-Specific Source Priority

When the question is about a specific topic, prioritize these sources:

| Topic | Priority Sources |
|-------|-----------------|
| **Supplements/Nutrition** | [host-32], PubMed, FDA, [host-36] |
| **Exercise/Training** | PubMed, ACSM, NSCA, Mayo Clinic |
| **Sleep** | PubMed, [host-40], Mayo Clinic, Harvard Health |
| **Heart/Cardiovascular** | AHA, NHLBI, PubMed, Cleveland Clinic |
| **Cancer** | NCI, ACS, Cochrane, PubMed |
| **Diabetes** | ADA, Joslin, NDEP, PubMed |
| **Mental Health** | NIMH, APA, PubMed, Mayo Clinic |
| **Medications** | FDA, EMA, PubMed, Cochrane |
| **Weight/Body Comp** | PubMed, [host-32], Harvard Health |
| **Longevity/Aging** | PubMed, NIA ([host-52]), Harvard Health |

## Evidence Grading Quick Reference

| Source Type | Starting GRADE Level | Notes |
|-------------|---------------------|-------|
| Cochrane systematic review | High | Gold standard |
| PubMed meta-analysis | High | Check heterogeneity |
| Large RCT (>500 participants) | High | Check funding/bias |
| Small RCT (<100) | Moderate | Underpowered risk |
| Observational/cohort | Low-Moderate | Confounding risk |
| Expert opinion/guidelines | Moderate | Based on evidence synthesis |
| [host-32] summary | Moderate | Well-referenced but secondary |
| Case report/series | Low | Anecdotal |
| Animal/in-vitro study | Very Low | Not directly applicable |
| Preprint (not peer-reviewed) | Very Low | Flag prominently |
| News article | N/A | Never grade as evidence |

## Red Flags to Watch For

When evaluating sources, flag these:
- **Industry-funded studies** without independent replication
- **Retracted papers** (check Retraction Watch)
- **Predatory journals** (check DOAJ for journal quality)
- **Supplements with proprietary blends** (can't verify doses)
- **N=1 or case report** presented as generalizable
- **Animal studies** presented as human-applicable
- **Relative risk** without absolute risk context
- **Correlation** presented as causation
