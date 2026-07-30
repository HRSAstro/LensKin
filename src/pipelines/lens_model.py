"""Lens mass model construction for parametric and phase-1 fits."""
import autofit as af
import autolens as al

from src.pipelines.priors import prior_from_cfg


def free_lens_centre_from_settings(settings):
    """Return True when the fit should optimize lens mass centre."""
    if "free_lens_centre" in settings:
        return bool(settings["free_lens_centre"])
    rec = settings.get("reconstruction")
    if rec is not None:
        return not rec.get("fix_lens", False)
    return False


def _lens_centre_priors_from_settings(settings, centre_prior_cfg=None):
    """
    Build ``centre_0`` / ``centre_1`` priors for a free lens centre.

    Uses ``settings['lens_priors']`` when present, otherwise a box of width
    ``2 * lens_centre_half_width`` around ``lens_mass_model`` values.
    """
    mass_cfg = settings["lens_mass_model"]
    c0 = float(mass_cfg["centre_0"])
    c1 = float(mass_cfg["centre_1"])
    half_width = float(settings.get("lens_centre_half_width", 0.05))
    lens_priors = settings.get("lens_priors", {})

    if centre_prior_cfg is not None:
        lo = float(centre_prior_cfg["lower_limit"])
        hi = float(centre_prior_cfg["upper_limit"])
        return (
            af.UniformPrior(lower_limit=lo, upper_limit=hi),
            af.UniformPrior(lower_limit=lo, upper_limit=hi),
        )

    priors = {}
    for key, default_centre in (("centre_0", c0), ("centre_1", c1)):
        if key in lens_priors:
            priors[key] = prior_from_cfg(lens_priors[key])
        else:
            priors[key] = af.UniformPrior(
                lower_limit=default_centre - half_width,
                upper_limit=default_centre + half_width,
            )
    return priors["centre_0"], priors["centre_1"]


def lens_galaxy_model_from_settings(
    settings,
    *,
    free_centre=None,
    centre_prior_cfg=None,
):
    """
    Return an ``af.Model(al.Galaxy, ...)`` for the lens from settings JSON.

    When ``free_centre`` is True, only ``mass.centre_0`` / ``mass.centre_1``
    are free; other mass parameters stay fixed at ``lens_mass_model`` values.
    """
    if free_centre is None:
        free_centre = free_lens_centre_from_settings(settings)

    mass_cfg = settings["lens_mass_model"]
    mass_kwargs = dict(
        einstein_radius=mass_cfg["einstein_radius"],
        ell_comps=(mass_cfg["elliptical_comps_0"], mass_cfg["elliptical_comps_1"]),
        slope=mass_cfg["slope"],
    )
    if free_centre:
        centre_0_prior, centre_1_prior = _lens_centre_priors_from_settings(
            settings,
            centre_prior_cfg=centre_prior_cfg,
        )
        mass = af.Model(al.mp.PowerLaw, **mass_kwargs)
        mass.centre_0 = centre_0_prior
        mass.centre_1 = centre_1_prior
    else:
        mass = af.Model(
            al.mp.PowerLaw,
            centre=(mass_cfg["centre_0"], mass_cfg["centre_1"]),
            **mass_kwargs,
        )

    shear_swap = settings.get("swap_shear_components", True)
    gamma_1 = (
        mass_cfg["shear_elliptical_comps_1"]
        if shear_swap
        else mass_cfg["shear_elliptical_comps_0"]
    )
    gamma_2 = (
        mass_cfg["shear_elliptical_comps_0"]
        if shear_swap
        else mass_cfg["shear_elliptical_comps_1"]
    )
    shear = af.Model(al.mp.ExternalShear, gamma_1=gamma_1, gamma_2=gamma_2)

    lens_kwargs = {
        "redshift": settings["redshift_lens"],
        "mass": mass,
        "shear": shear,
    }

    if (
        "multipole_m3_elliptical_comps_0" in mass_cfg
        and "multipole_m3_elliptical_comps_1" in mass_cfg
    ):
        m3 = af.Model(
            al.mp.PowerLawMultipole,
            m=3,
            einstein_radius=mass_cfg["einstein_radius"],
            slope=mass_cfg["slope"],
            multipole_comps=(
                mass_cfg["multipole_m3_elliptical_comps_0"],
                mass_cfg["multipole_m3_elliptical_comps_1"],
            ),
        )
        m3.centre = mass.centre
        lens_kwargs["multipole_m3"] = m3

    if (
        "multipole_m4_elliptical_comps_0" in mass_cfg
        and "multipole_m4_elliptical_comps_1" in mass_cfg
    ):
        m4 = af.Model(
            al.mp.PowerLawMultipole,
            m=4,
            einstein_radius=mass_cfg["einstein_radius"],
            slope=mass_cfg["slope"],
            multipole_comps=(
                mass_cfg["multipole_m4_elliptical_comps_0"],
                mass_cfg["multipole_m4_elliptical_comps_1"],
            ),
        )
        m4.centre = mass.centre
        lens_kwargs["multipole_m4"] = m4

    return af.Model(al.Galaxy, **lens_kwargs)


def lens_centre_from_instance(instance, settings):
    """Read lens mass centre from a fit instance, or fall back to settings."""
    if hasattr(instance, "galaxies") and hasattr(instance.galaxies, "lens"):
        mass_centre = instance.galaxies.lens.mass.centre
        return float(mass_centre[0]), float(mass_centre[1])
    mass_cfg = settings["lens_mass_model"]
    return float(mass_cfg["centre_0"]), float(mass_cfg["centre_1"])
