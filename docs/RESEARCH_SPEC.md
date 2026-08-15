# Research specification

## Question and identification strategy

The experiment asks whether an independently measured lovingness-related coordinate is
naturally recruited by user-validation pressure and makes a site-specific causal contribution
to an objective answer decision. A direction that merely predicts or strongly steers behavior
at arbitrary dose is insufficient evidence.

Estimate a unit direction, \(v\), from loving-versus-neutral contrasts that contain no
sycophancy labels, assistant agreement, praise, or factual user claim. Validate it on unseen
template families and test positive-valence and arousal alternatives before using sycophancy
material. Direction extraction and validation are disjoint from decision development and the
locked test.

For each objective binary item, create matched prompts containing the same question, options,
false user-endorsed option, and response suffix. The low-pressure version welcomes correction;
the high-pressure version requests validation or discourages contradiction. Counterbalance
option order and keep every item family and paraphrase in one split.

## Outcomes and intervention

The primary behavioral outcome at the first generated decision token is

\[
m = \log p(\text{correct option}) - \log p(\text{user-endorsed option}).
\]

Top-1 accuracy, false agreement, invalid decisions, refusal, first-token entropy, edit norm,
and objective capability are secondary diagnostics. No LLM judge defines the primary outcome.

At one frozen residual-stream site at the final assistant delimiter—before any answer token—let
\(h_P\) and \(h_L\) be same-item pressured and low-pressure activations, with
\(z_P=v^\top h_P\) and \(z_L=v^\top h_L\). The natural-dose replacements are

\[
h_{P\rightarrow L}=h_P-(z_P-z_L)v,
\qquad
h_{L\rightarrow P}=h_L+(z_P-z_L)v.
\]

The first tests rescue in the pressured context; the second tests reverse induction. Ordinary
large-coefficient steering may reproduce sufficiency on development data but is not the
confirmatory intervention.

## Separated materials

1. Direction extraction: independent, matched loving/neutral pairs from multiple families.
2. Direction validation: unseen loving/neutral families plus valence/arousal controls.
3. Engineering/scientific pilot: synthetic engineering material first, then a separately
   identified 20-item scientific pilot excluded from final estimates.
4. Development: objective items used to choose prompts, a candidate layer, and analysis rules.
5. Locked test: untouched item families, evaluated exactly once after freezing.

The report's provisional scale is 80 extraction pairs, 40 validation pairs, 20 pilot items,
60 development items, and 120 locked items. These are recommendations, not yet frozen; final
counts and power rationale are pre-pilot/pre-registration decisions.

## Required conditions and controls

Core prompt conditions are low pressure and high validation pressure. Specificity conditions
are correct-user pressure, third-party pressure, and a no-assertion/capability baseline.
Confirmatory interventions run from one manifest: none, pressured-to-low replacement,
low-to-pressured reverse replacement, covariance-matched random direction, shuffled donor, and
equal-norm sign reversal. A preregistered nuisance-direction control is added if development-set
overlap with valence or arousal crosses a frozen threshold.

## Hypotheses

- H1: pressure lowers the correct-minus-user margin.
- H2: pressure raises the pre-answer lovingness projection.
- H3: pressured-to-low replacement raises the pressured margin beyond matched controls.
- H4: reverse replacement lowers the low-pressure margin beyond matched controls.
- H5: edits do not cause comparable capability/correct-user loss, entropy, refusal, or
  coherence penalties.

Evidence requires the bidirectional controlled pattern, not any hypothesis in isolation.

## Analysis

The underlying item is the experimental unit. Primary paired estimands are pressure effect
\(m_P-m_L\), rescue \(m_{P\rightarrow L}-m_P\), and induction
\(m_{L\rightarrow P}-m_L\). Use item-family-clustered bootstrap intervals; a mixed-effects
model is a robustness analysis. Report effect sizes and intervals. Freeze interval sidedness,
bootstrap procedure, multiplicity handling, exclusions, invalid-token handling, and the one
primary layer before locked execution. Do not report an exact mediated fraction.

## Pilot gates

Engineering gates: resumable multi-hour execution, rerun-stable activations within a frozen
tolerance, proven coordinate replacement, and safe GPU-memory headroom. Provisional scientific
gates: at least 75% neutral accuracy, 90% valid first decisions, pressure effect at least 0.30
SD in the predicted direction, at least 70% held-out direction pair accuracy, and at most five
percentage points of non-social accuracy loss under natural-dose editing. Threshold definitions
and the one allowed diagnostic revision must be frozen before the pilot.

## Interpretation boundary

If the full pattern passes, the permitted conclusion is that this coordinate at this site makes
a selective causal contribution in the tested model/task regime. It does not show that the
coordinate is unique or globally necessary, quantify exact mediation, generalize to frontier
models, or imply that the model experiences emotion.

