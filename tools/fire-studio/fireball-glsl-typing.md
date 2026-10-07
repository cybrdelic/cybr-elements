# Upper-boundary coefficient typing

The 384 by 384 by 64 blast domain has extent 8 by 8 by 4. Both upper-boundary apply coefficients are therefore 6. V7 generated `6 * float`, which GLSL ES rejects. The generator now emits `6.0` for integral coefficients; coefficient values, projection equations, correction budgets and transport remain unchanged. Existing nonintegral coefficient text is retained exactly.

The regression fixture is the actual failing v7 fragment. Its corrected form differs by exactly two numeric literals. CPU/static checks cover 76 preset identities, both supported grid selections, five domain forms and 718 generated shader stages, including the optional material ledger. Full CPU checks pass 496 tests across 70 suites, plus package and asset validation. All normal/object stages and all blast stages except that apply fragment are byte-identical to v7. Static checks do not replace native shader compilation; a coordinated brief native check remains required before publication.

This change contains no decision batching or claimed realtime optimization. Deployed v7 and the separate batching experiment are preserved.
