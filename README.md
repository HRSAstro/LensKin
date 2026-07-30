# LensKin

PyAutoLens/PyAutoFit workspace for fitting lensed ALMA uv spectral-line cubes with GalPaK or KinMS source models.

## Repository layout

```
LensKin/
├── config/                 # AutoFit / AutoLens YAML configuration
├── settings/
│   ├── runners/            # Fit-pipeline JSON settings
│   └── dataprep/           # Data-prep JSON settings
├── scripts/
│   ├── run_fit.py          # Generic fit entry point (all normalization modes)
│   ├── run_pixelized_fit.py # Legacy alias for two-phase KinMS fits
│   ├── run_dataprep.py     # Generic data-prep entry point
│   ├── make_cornerplot.py  # Corner plot from a completed run
│   ├── test_phase1_pixelization.py   # Phase-1 pixelized reconstruction tests
│   ├── profile_phase1_regularization.py  # Reg-coefficient / FoM diagnostics
│   ├── check_moment0_noise.py        # Moment-0 vs channel noise diagnostic
│   ├── generate_unlensed_mock_and_diagnose.py  # Unlensed KinMS self-mock + truth diagnostics
│   ├── generate_lensed_mock_and_diagnose.py    # Lensed KinMS self-mock + parametric truth diagnostics
│   ├── generate_lensed_mock_pixelized_and_diagnose.py  # Lensed mock + KinMSPixelized truth diagnostics
│   ├── trial_source_grid_regularization.py    # Phase-1 grid/reg scan vs pixelized truth floor
│   ├── diagnose_mode2_fit.py         # Post-fit dirty mom0 residual diagnostics
│   ├── runners/            # Target-specific fit wrappers
│   ├── dataprep/           # Target-specific data-prep wrappers
│   ├── plotting/           # Ad-hoc plotting scripts
│   ├── slurm/              # Slurm submit wrappers (_run_fit.sh, submit_*.sh)
│   └── tutorial.py         # Synthetic tutorial fit
├── src/
│   ├── pipelines/          # Shared runner / dataprep logic
│   ├── analysis/
│   ├── dataset/
│   ├── fit/
│   ├── grid/
│   ├── mask/
│   ├── model/
│   └── utils/
│       ├── ...
│       └── primary_beam.py    # Gaussian primary-beam attenuation (HPBW = 1.13λ/D)
├── tests/                  # Unit tests (pytest)
└── output/                 # Search results (generated)
```

## Running fits

From the repository root:

```bash
python scripts/run_fit.py --settings settings/runners/SPT0538_CO9-8.json
```

Or use a target wrapper (same behaviour, default settings baked in):

```bash
python scripts/runners/SPT0538_CO9-8.py
python scripts/runners/SPT0538_mockSMBH.py
python scripts/runners/HERMES_J021830.5-053124.py
python scripts/runners/SPT0538_CO9-8_pixelized.py
python scripts/runners/kinms_mock_pixelized.py
python scripts/runners/kinms_mock_parametric_flux.py
```

Override settings with `--settings /path/to/custom.json`.

`scripts/run_fit.py` dispatches automatically on `normalization_mode` in the settings file. `scripts/run_pixelized_fit.py` remains as a legacy entry point for two-phase KinMS fits.

## KinMS source normalization modes

KinMS fits support three source normalization schemes, selected with the top-level `normalization_mode` key in the runner settings JSON.

| Mode | Settings value | Phase 1 | Source model | Flux / luminosity |
|------|----------------|---------|--------------|-------------------|
| 1 — Fully parametric | `"parametric"` | No | `KinMS` exponential disk (`effective_radius`) | `intensity` is a free fit parameter |
| 2 — Parametric shape, phase-1 flux | `"parametric_flux_from_phase1"` | Yes | `KinMS` exponential disk | `intensity` fixed to integrated flux from phase-1 pixelized reconstruction |
| 3 — Pixelized source | `"pixelized"` | Yes | `KinMSPixelized` cloudlets from phase-1 SB map | Spatial structure and total flux fixed from phase 1; only kinematics are fitted in phase 2 |

### Mode 1 — Fully parametric (`parametric`)

Single-phase fit. No `reconstruction` block is required.

- Surface brightness: parametric exponential disk (`effective_radius`)
- Intensity: free `intensity` prior
- Example: `settings/runners/SPT0538_mockSMBH.json`

```json
{
  "model_name": "KinMS",
  "normalization_mode": "parametric",
  "priors": {
    "intensity": {"type": "LogUniformPrior", "lower_limit": 0.001, "upper_limit": 0.1},
    "effective_radius": {"type": "LogUniformPrior", "lower_limit": 0.004, "upper_limit": 0.4}
  }
}
```

### Mode 2 — Parametric source, phase-1 flux normalization (`parametric_flux_from_phase1`)

Two-phase fit. Requires a `reconstruction` block (same phase-1 pixelized source reconstruction as mode 3).

- Phase 1: pixelized source reconstruction on velocity-averaged visibilities
- Phase 2: parametric `KinMS` disk with free `effective_radius` and kinematic parameters
- Intensity: `intensity` is set to the velocity-integrated flux of the phase-1 SB map (Jy/km/s, matching KinMS `intFlux`) and is not fitted
- Example: `settings/runners/kinms_mock_parametric_flux.json`

```json
{
  "model_name": "KinMS",
  "normalization_mode": "parametric_flux_from_phase1",
  "reconstruction": {
    "mesh_type": "delaunay",
    "regularization": {"type": "constant_split", "prior_type": "fixed", "value": 1e5}
  },
  "priors": {
    "effective_radius": {"type": "LogUniformPrior", "lower_limit": 0.03, "upper_limit": 0.07}
  }
}
```

Do not include an `intensity` prior; it is fixed automatically after phase 1.

### Mode 3 — Pixelized source (`pixelized`)

Two-phase fit. Requires a `reconstruction` block.

- Phase 1: pixelized source reconstruction on velocity-averaged visibilities
- Phase 2: `KinMSPixelized` — phase-1 SB map converted to KinMS `inClouds` / `flux_clouds`; total flux passed as fixed `intFlux`
- Only kinematic parameters and lens mass are fitted in phase 2 (no `intensity` or `effective_radius`)
- **Sky-plane `inClouds`:** phase-1 maps are already projected morphologies. Inclination/PA are applied only to LOS velocities (`vLOS_clouds`), not by re-projecting cloud positions (which would double-count \(\cos i\) and brighten peaks)
- **Cube axes:** KinMS returns `(x, y, v)`; LensKin stores `(v, y, x)` for autolens. Source centre placement uses `phaseCent=[x, y]` with optional `flip_kinms_y_before_lensing` for y-sense matching
- Example: `settings/runners/SPT0538_CO9-8_pixelized.json`

```json
{
  "model_name": "KinMSPixelized",
  "normalization_mode": "pixelized",
  "reconstruction": {
    "mesh_type": "delaunay",
    "regularization": {"type": "constant_split", "prior_type": "fixed", "value": 1e5},
    "clouds_per_pixel": 1024,
    "disk_scale_height_kpc": 0.1,
    "max_radius": null,
    "sb_input_units": "jy_per_pixel_per_channel"
  },
  "priors": {
    "maximum_velocity": {"type": "UniformPrior", "lower_limit": 200.0, "upper_limit": 400.0}
  }
}
```

#### Cloud sampling (`KinMSPixelized`)

Phase-1 / truth SB maps on the KinMS grid are turned into cloudlets by `in_clouds_and_flux_from_sb_map`:

1. Convert the map to velocity-integrated flux (`Jy km/s/pixel`) using `sb_input_units`
2. Spawn `clouds_per_pixel` clouds per lit pixel (uniform jitter in the pixel; optional exponential `z` scale height)
3. Pass relative `flux_clouds` weights plus total `intFlux` into KinMS (`cleanOut=True` → `cube.sum() * dv == intFlux`)

| Setting | Default | Notes |
|---------|---------|-------|
| `reconstruction.clouds_per_pixel` | `1024` | Higher density reduces spatial sampling speckles; total flux is conserved at any density |
| `reconstruction.disk_scale_height_kpc` | `0.1` | Converted to source-plane arcsec at `redshift_source` |
| `reconstruction.max_radius` | `null` | Optional arcsec clip of clouds about the phase centre; `null` = no clip |
| `reconstruction.sb_input_units` | `"jy_per_pixel_per_channel"` | Or `"jy_kms_per_pixel"` if the map is already moment-0 |

**Total flux** through the cloud step is conserved exactly. **Spatial** residuals vs a smooth truth map are a cloudlet / re-binning floor (typically \(\lesssim 1\sigma_{\mathrm{dirty}}\) at 1024 clouds on the wide-velocity mock).

For backward compatibility, `model_name: "KinMSPixelized"` without an explicit `normalization_mode` is treated as `"pixelized"`.

GalPaK fits always use mode 1 semantics (`normalization_mode` must be `"parametric"` or omitted).

## Phase-1 pixelized reconstruction

Modes 2 and 3 run a preliminary phase-1 fit before KinMS. Phase 1 builds a **moment-0** `Interferometer` dataset (complex mean over spectral channels), reconstructs the lensed source on the source plane, and passes the SB map (and optionally lens centre / flux) to phase 2.

### Recommended settings (interferometer mock / ALMA cubes)

Validated on `kinms_mock` data:

| Setting | Recommended value |
|---------|-------------------|
| `mesh_type` | `"delaunay"` |
| `image_mesh_shape` | `[30, 30]` |
| `delaunay_edge_pixels` | `30` |
| `regularization.type` | `"constant_split"` (Delaunay analogue of `constant`) |
| `regularization.value` | `1e5` (fixed) or log-uniform prior around this scale |
| `fix_lens` | `false` — free lens centre works well with fixed or optimised λ |
| `search.use_jax_gradient` | `false` (Delaunay triangulation is not JAX-differentiable) |

Example `reconstruction` block:

```json
"reconstruction": {
  "fix_lens": false,
  "mesh_type": "delaunay",
  "mask_n_pixels": 128,
  "mask_radius": 3.0,
  "image_mesh_shape": [30, 30],
  "delaunay_edge_pixels": 30,
  "clouds_per_pixel": 1024,
  "disk_scale_height_kpc": 0.1,
  "max_radius": null,
  "sb_input_units": "jy_per_pixel_per_channel",
  "moment0": {
    "sigma_mode": "independent_mean",
    "sigma_scale": 1.0,
    "uv_mode": "average"
  },
  "centre_prior": {"lower_limit": -0.5, "upper_limit": 0.5},
  "regularization": {
    "type": "constant_split",
    "prior_type": "fixed",
    "value": 1e5
  },
  "search": {
    "path_prefix": "kinms_mock_pixelized",
    "name": "reconstruction",
    "optimizer": "LBFGS",
    "use_jax_gradient": false,
    "number_of_cores": "auto",
    "maxiter": 1000
  }
}
```

To optimise the regularization coefficient with LBFGS, use `"prior_type": "log_uniform"` with bounds ±3× around the tuned value (e.g. `33333`–`300000` for centre `1e5`).

### Mesh and regularization pairing

| Mesh | Regularization types |
|------|----------------------|
| `rectangular_adapt_density`, `rectangular_uniform` | `constant`, `adapt` |
| `delaunay` | `constant_split`, `adapt_split` |

`adapt` / `adapt_split` require a dirty-image adapt map (built automatically from the dataset). `AdaptSplit` uses three parameters (`inner_coefficient`, `outer_coefficient`, `signal_scale`) on a very different scale from a single `constant`/`constant_split` coefficient (~`1e5` for interferometer data).

### JAX gradients (`use_jax_gradient`)

Setting `"use_jax_gradient": true` in `reconstruction.search` selects `JAXLBFGS`, which passes analytical JAX gradients (`fitness.grad`) to scipy's L-BFGS-B. That avoids finite-difference stepping with a single `eps`, which is problematic when lens centres (~0.2″) and regularization coefficients (~`1e5`) are optimised together.

LensKin also sets `"use_jax": true` by default on the phase-1 dataset (JAX sparse UV operator). Both flags apply **only to phase-1 LBFGS**; phase-2 Nautilus uses a separate code path.

#### When JAX gradients work

| Requirement | Why |
|-------------|-----|
| **Rectangular mesh** (`rectangular_adapt_density`, `rectangular_uniform`, `rectangular_adapt_image`) | Mapper/interpolator is JAX-differentiable end-to-end |
| **`use_jax: true`** on the dataset (default) | Sparse operator and analysis run in JAX |
| **Phase-1 LBFGS** with mixed-scale free parameters | Main benefit: no shared `eps` across arcsec and coefficient scales |
| **`constant` or `adapt`** regularization on rectangular meshes | Standard schemes; no Delaunay triangulation callback |

Example (rectangular mesh, optimising λ and lens centre):

```json
"mesh_type": "rectangular_adapt_density",
"regularization": {
  "type": "constant",
  "prior_type": "log_uniform",
  "lower_limit": 1e5,
  "upper_limit": 1e7
},
"search": {
  "optimizer": "LBFGS",
  "use_jax_gradient": true
}
```

#### When JAX gradients are disabled or unavailable

| Condition | Reason |
|-----------|--------|
| **`mesh_type: delaunay`** | Triangulation uses `jax.pure_callback`, which has no JVP; LensKin **auto-disables** `use_jax_gradient` and `use_jax` |
| **`constant_split` / `adapt_split`** on Delaunay | Same non-differentiable triangulation (current validated mock setup) |
| **Phase-2 Nautilus** | `use_jax_gradient` does not apply |

#### Practical summary

| Setup | Use JAX gradient? |
|-------|-------------------|
| **Delaunay + `constant_split` @ `1e5`** (validated mock) | **No** — keep `use_jax_gradient: false` |
| **Rectangular + `constant`**, optimising λ and lens centre | **Yes** — primary use case |
| **Rectangular + `adapt`**, optimising reg params and centre | **Yes** (less tested than `constant`) |
| **Fixed λ, only lens centre free** on rectangular | Optional — finite-difference LBFGS is often sufficient |

#### What JAX gradients fix (and do not fix)

**Fix:** scipy's single `eps` across very different parameter scales during LBFGS.

**Do not fix:**

- `log_evidence` Cholesky failures during optimisation — set `search.figure_of_merit` to `"log_likelihood_with_regularization"` if needed (see diagnostics note below)
- Delaunay mesh limitations — use scipy LBFGS with `use_jax_gradient: false`
- Poor LBFGS landscapes — consider Nautilus on regularization parameters instead

### Phase-1 diagnostics

Test phase-1 in isolation (fixed lens from `lens_mass_model`):

```bash
python scripts/test_phase1_pixelization.py \
  --settings settings/runners/kinms_mock_pixelized.json

# Pipeline LBFGS path (same as run_fit.py phase 1)
python scripts/test_phase1_pixelization.py \
  --settings settings/runners/kinms_mock_pixelized.json \
  --mode pipeline
```

Scan regularization figures of merit vs coefficient:

```bash
python scripts/profile_phase1_regularization.py \
  --settings settings/runners/kinms_mock_pixelized.json --mode scan
```

Compare moment-0 and single-channel noise:

```bash
python scripts/check_moment0_noise.py \
  --settings settings/runners/kinms_mock_pixelized.json
```

Phase-1 LBFGS maximizes `figure_of_merit` from the analysis class. For Delaunay + `AdaptSplit` optimisation, set `search.figure_of_merit` to `"log_likelihood_with_regularization"` if `log_evidence` Cholesky factors fail. With `constant_split` and fixed λ, the default evidence-based metric is usually stable.

Phase-1 reconstruction uses `lens_mass_model` for the lens. With `"fix_lens": true`, only regularization is free in phase 1. With `"fix_lens": false`, the lens centre is also fitted (other mass parameters remain fixed from `lens_mass_model`).

Mock validation settings:

- `settings/runners/kinms_mock_pixelized.json` — mode 3 (`KinMSPixelized`)
- `settings/runners/kinms_mock_parametric_flux.json` — mode 2 (`parametric_flux_from_phase1`)
- `settings/runners/kinms_mock_lensed_pixelized.json` — lensed mock + pixelized diagnostics
- `settings/runners/kinms_mock_lensed_pixelized_widevel.json` — same with padded spectral axis (avoids \(v\sin i\) truncation)

Submit to Slurm:

```bash
bash scripts/slurm/submit_kinms_mock_pixelized.sh
bash scripts/slurm/submit_kinms_mock_parametric_flux.sh
```

## Mock validation (KinMS self-mocks)

Self-mocks reuse template ALMA UV coverage and `sigma_statwt` noise maps from an existing dataprep product, replace visibilities with a KinMS → lens → NUFFT model, and score truth (or phase-1) forward models.

### Lensed parametric mock

```bash
python scripts/generate_lensed_mock_and_diagnose.py \
  --settings settings/runners/kinms_mock_lensed_pixelized_widevel.json
```

Ceiling check: lensing the frozen source cube and dirty-imaging should give χ² ≈ 0 on a noiseless mock.

### Lensed pixelized-SB truth diagnostics

Fixes the SB map to the truth channel-mean cube, runs `KinMSPixelized` at truth kinematics, and writes source-plane + dirty residual diagnostics:

```bash
# Generate mock (noiseless by default) + diagnose
python scripts/generate_lensed_mock_pixelized_and_diagnose.py \
  --settings settings/runners/kinms_mock_lensed_pixelized_widevel.json

# Re-run diagnostics only
python scripts/generate_lensed_mock_pixelized_and_diagnose.py \
  --settings settings/runners/kinms_mock_lensed_pixelized_widevel.json \
  --skip-generate

# Optional: inject Gaussian visibility noise N(0, σ) from the template σ map
python scripts/generate_lensed_mock_pixelized_and_diagnose.py \
  --settings settings/runners/kinms_mock_lensed_pixelized_widevel.json \
  --add-noise
```

Useful outputs under `output/.../lensed_pixelized_truth_diagnostics/`:

| File | Content |
|------|---------|
| `pixelized_source_mom0.png` | Source-plane KinMS cube mom0 (should be a focussed disk, not a ring) |
| `source_plane_truth_vs_pixelized.png` | Truth vs cloudlet-sampled source mom0 |
| `dirty_mom0_*_over_sigma.png` | Dirty mom0 residuals in units of Monte-Carlo dirty-image σ |
| `channel_residuals_*_over_sigma.png` | Per-channel residuals / σ (±5σ colour bar) |

Visibility σ always comes from the template `sigma_statwt` (χ² weights). The mock is **noiseless** unless `--add-noise` is set. Residual `/σ` maps use a Monte-Carlo dirty-image noise cube from that same σ.

For high-\(v\sin i\) disks, set `mock_pad_channels_each_side` (widevel settings use `8`) so the spectral window is wider than the projected rotation; otherwise edge channels are truncated and pixelized SB underfills the line wings.

### Phase-1 grid / regularization trials

Score how phase-1 source-grid size and regularization set the residual floor relative to a frozen-SB baseline:

```bash
python scripts/trial_source_grid_regularization.py \
  --settings settings/runners/kinms_mock_lensed_pixelized_widevel.json \
  --source-n-pixels 128,256,512 \
  --reg 1e3,1e4,1e5,1e6 \
  --mesh-shapes 20x20,30x30 \
  --mesh rectangular
```

Writes `output/.../grid_reg_trials/trial_summary.csv`, heatmaps, and per-trial dirty `/σ` residual plots. Prefer `--mesh rectangular` for scans; Delaunay matches production but is heavier.

## Primary beam correction

LensKin supports an optional Gaussian primary-beam (PB) attenuation in the forward model, following Stacey et al. (2024, A&A, [arXiv:2403.04850](https://arxiv.org/abs/2403.04850)), §3.2. The PB is modelled as a Gaussian with half-power beam width HPBW = 1.13 λ/D (where D = 12 m for ALMA). The wavelength is computed from the mean of the input channel frequencies — no manual `wavelength_m` entry is needed.

When enabled, the PB map is applied as a diagonal image-plane operator: each real-space channel image is multiplied by the PB before the NUFFT (phase 2) or before the Autolens transformer (phase 1). Visibility noise maps are not modified. Dirty images remain in attenuated (observed) units.

### Settings

Add a `primary_beam` block to the runner settings JSON:

```json
"primary_beam": {
  "enabled": true,
  "dish_diameter_m": 12.0,
  "pointing_arcsec": [0.0, 0.0]
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Enable/disable PB correction |
| `dish_diameter_m` | `12.0` | Antenna diameter in metres |
| `pointing_arcsec` | `[0.0, 0.0]` | Pointing centre offset `[y, x]` in arcsec (default: phase centre) |

When `enabled` is `false` or the block is absent, the pipeline behaves identically to previous versions. At Band 7 (~350 GHz) with a 5″ field, the PB attenuation at the field edge is only a few percent; the correction matters more for wide-field or lower-frequency observations.

## Corner plots

After a completed Nautilus search:

```bash
python scripts/make_cornerplot.py /path/to/run_hash_directory
```

Writes `cornerplot.png` in the run directory, plotting free parameters only.

## Exporting uv FITS products (CASA)

Inside a CASA environment:

```bash
python scripts/run_dataprep.py --settings settings/dataprep/SPT0538_CO9-8.json
```

Or:

```bash
casa -c scripts/run_dataprep.py --settings settings/dataprep/SPT0538_CO9-8.json
```

## Dependencies

LOCAL

python == 3.8

pip install scipy == 1.10.1

pip install numpy == 1.24.3

pip install autofit == 2024.5.16.0

pip install autolens == 2024.5.16.0

pip install pynufft == 2024.1.2

pip install galpak == 1.34.0

pip install kinms == 3.0.7

COSMA

python == 3.9
