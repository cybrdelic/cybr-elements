# Fire Studio release audit — September 29, 2026

This audit covers packaging, dependency integrity, release copy and research leakage. It does not certify current browser appearance, frame rate or offline visual parity.

## Corrected defects

The previous validator accepted missing plain HTML references such as `studio.css`, unprefixed fetch paths and CSS `url()` assets. It also did not check the dynamically selected source previews or object binaries. The package now validates these references, rejects paths escaping the deployment subtree and verifies object/tree bytes against their supplied SHA-256 manifests. Native source texture byte counts are checked against the runtime's upload dimensions.

Mixed `studio-rc-3` and `studio-rc-5` queries could load old transitive modules and create two ES module instances of the preset catalog. The packaged output now uses a single content-derived key across imports, classic shader loaders, stylesheets, static assets, computed object fields, source previews and tree requests. Editing a source or binary changes that key. Package files are built from one byte snapshot, so the copied files and the recorded hashes cannot diverge if a source changes during the copy.

Selected JavaScript must be reachable from an entry page; adding an orphan script causes the build to fail. Historical experiment directories, QA tools and capture sequences are excluded. The object provenance manifest is now included. `--verify` checks a completed directory or ZIP for byte/hash agreement, transformed JavaScript syntax, duplicate paths and unrecorded files before deployment.

The release README now describes current interaction and graphics requirements, marks 3D volume as experimental and names the incomplete physical features. Old dated development claims remain in the research history/performance documentation. The candidate does not claim mobile support, physical branch collapse, ember ignition, guaranteed FPS or offline quality parity.

## Checks performed

- Six Python release tests passed, including cache consistency, deployment path handling, dynamic asset integrity, syntax of transformed modules and corrupted/unrecorded artifact rejection.
- Source package validation passed with 72 selected runtime/provenance files, about 74.8 MB before ZIP compression. All selected modules were reachable and binary manifests matched.
- A packaging-proof snapshot at `work/fire-release-audit/candidate/` and `candidate.zip` was built and independently verified. The snapshot build was `668334a162f86c03`; its ZIP was 43,176,181 bytes. It predates the final integrated runtime edits and must not be substituted for the final release.
- AI Slop Check inspected the concrete development `fire-live/` tree and the actual proof package. The development tree scored 100/100, dominated by duplicated GLSL and old experiment code. The top flagged library and shader lines were inspected: input placeholder attributes and ordinary full-screen triangle/float-extension GLSL were false positives. The package scored 0/100 across 47 scanned text files. This heuristic measures boilerplate/unfinished copy signals; it does not measure rendering quality or establish authorship.

The saved checker results are `work/fire-release-slop-audit.md` and `work/fire-release-audit/package-slop-audit.md`. Re-run the checker and artifact verifier against the final package after all agents finish.

## Remaining release gates

Current local browser automation is blocked, and that boundary was not bypassed. Native captures, shader compilation, historical browser traces and deterministic state tests are the available evidence in this session. A current live-browser sequence on the demonstration machine is still needed for smoke/flame motion, dense-fire artifacts and actual completed FPS. No physical mobile device was available to close the memory/compatibility/performance gate.

Volume's requested speed parity remains unmet in the recorded browser measurements. Trees retain moisture, char, fissure/leaf state and reviewed mesh geometry but lack physical fracture/collapse; prototype car/house/mannequin geometry remains an experiment. These are implementation limits, not issues a packaging pass can fix.

The local Pages checkout points to `cybrdelic/cybrdelic.github.io` on `master` and had a clean worktree when inspected. The configured Pages source still needs confirmation at publish time. There is no Fire Studio deployment workflow in the inspected local `.github/workflows` directory. No commit, push or deployment was performed by this audit.

Follow `RELEASE.md` to build a final candidate, verify its exact bytes, publish only the package subtree and compare representative public hashes. Keep the open gates in `release.json` until their evidence exists.
