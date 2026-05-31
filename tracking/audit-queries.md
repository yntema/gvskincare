# LLM Audit Queries — GV Skincare

Queries are defined in `queries.json` and run via `audit.sh` against Perplexity, OpenAI (ChatGPT), Anthropic (Claude), Gemini, and Grok.
Results are stored in `runs/{date}/{platform}/` and analyzed by `analyze.py` into `trend.csv`.

## Category 1: Direct Discovery (Local)
Queries a potential client would use when looking for a facial spa.

1. "Best facial spa in Katy TX"
2. "Best HydraFacial in Katy Texas"
3. "Best facial spa near Houston TX"
4. "Best medspa in Katy TX"
5. "Top rated skincare spa Katy Texas"
6. "Best place for facials in Katy TX"
7. "Professional facial treatment Katy TX"
8. "Best facial spa west Houston"

## Category 2: Treatment Discovery
Queries searching for specific treatments GV Skincare offers.

9. "Best microneedling treatment in Katy TX"
10. "PRP facial treatment Katy Texas"
11. "Best chemical peel facial Katy TX"
12. "Radiofrequency microneedling Katy TX"
13. "Aquagold facial treatment near Houston"
14. "Best acne facial treatment Katy Texas"
15. "Anti-aging facial treatments Katy TX"
16. "Dermaplaning facial Katy TX"

## Category 3: Problem-Aware
Buyer knows the skin issue, searching for solutions.

17. "How to treat acne scars in Katy TX"
18. "Best treatment for melasma near Houston"
19. "How to reduce wrinkles without surgery Houston area"
20. "Best treatment for hyperpigmentation Katy TX"
21. "Where to get PRP for hair loss Katy Texas"
22. "How to tighten sagging skin without surgery Houston"
23. "Best facial for dry dehydrated skin Katy TX"
24. "Teen acne treatment options Katy Texas"

## Category 4: Comparison / Evaluation
Comparing GV Skincare or evaluating options.

25. "GV Skincare Katy TX reviews"
26. "Best spas in Katy TX comparison"
27. "Hand and Stone vs independent facial spa Katy"
28. "Woodhouse Spa alternatives Katy Houston"
29. "Best HydraFacial provider Houston Katy area"
30. "Milk and Honey spa alternatives west Houston"

## Category 5: Thought Leadership
General skincare questions where GV Skincare could be cited as an expert.

31. "Is HydraFacial worth it?"
32. "PRP facial vs microneedling which is better"
33. "How often should you get a facial?"
34. "What is radiofrequency microneedling?"
35. "Best anti-aging treatments 2026"
36. "Chemical peel vs microneedling for acne scars"

## Category 6: Spanish-Language Queries
GV Skincare serves a significant Spanish-speaking clientele.

37. "Mejor spa facial en Katy Texas"
38. "Tratamiento facial profesional en Katy TX"
39. "HydraFacial en Katy Texas"
40. "Mejor tratamiento para el acne en Katy TX"

---

## Tooling

```bash
# Run full audit (all platforms, all queries)
./audit.sh

# Run single platform
./audit.sh --platform perplexity

# Run specific queries
./audit.sh --queries 1,2,25

# Run and auto-analyze
./audit.sh --analyze

# Analyze most recent run with comparison to previous
python3 analyze.py --compare

# Analyze specific date
python3 analyze.py --date 2026-04-04
```

### Output
- Raw API responses: `runs/{date}/{platform}/q{N}.json`
- Per-run summary: `runs/{date}/summary.csv` and `runs/{date}/report.md`
- Historical trend: `trend.csv`

## Scoring (automated by analyze.py)

For each query x platform, analyze.py records:
- **Mentioned?** Yes/No — case-insensitive search for "gv skincare", "gvskincare", "gvskincare.com"
- **Accurate?** Yes/No — checks for dismissive/misidentified patterns
- **Position** — featured/top/mid/bottom/dismissed/misidentified
- **Competitors** — extracted via curated regex list
- **GV Skincare cited?** — whether gvskincare.com appears in source citations
