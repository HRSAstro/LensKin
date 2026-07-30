import os, sys
import numpy as np

# NOTE:
try:
    import autolens as al
except:
    print("\'autolens\' could not be imported")

# NOTE:
# from src.grid.grid import (
#     Grid3D,
# )
from src.grid.grid import Grid3D
from src.mask.mask import (
    Mask3D,
)


def source_grid_bounding_box_from_cfg(source_cfg):
    """
    Return ``[y_min, y_max, x_min, x_max]`` in arcsec, or ``None``.

    Accepts either a ``bounding_box`` list or explicit ``xmin``/``xmax``/
    ``ymin``/``ymax`` keys.
    """
    if "bounding_box" in source_cfg:
        return list(source_cfg["bounding_box"])
    keys = ("ymin", "ymax", "xmin", "xmax")
    if all(key in source_cfg for key in keys):
        return [
            source_cfg["ymin"],
            source_cfg["ymax"],
            source_cfg["xmin"],
            source_cfg["xmax"],
        ]
    return None


def source_grid_from_settings(settings):
    """
    KinMS source-plane grid (phase-2 cube generation).

    Defaults to ``DEFAULT_KINMS_SOURCE_N_PIXELS`` (256) and top-level
    ``real_space_width``. The image-plane ``n_pixels`` is **not** reused here —
    a coarse fit grid (e.g. 40²) must not drive KinMS resolution. An optional
    ``source_grid`` block can override ``n_pixels``, ``real_space_width``, or
    define a bounding box without changing the image-plane grid.
    """
    source_cfg = settings.get("source_grid", {})
    n_pixels = source_cfg.get("n_pixels", kinms_source_n_pixels_from_settings(settings))
    real_space_width = source_cfg.get("real_space_width", settings["real_space_width"])
    pixel_scale = source_cfg.get(
        "pixel_scale",
        settings.get("pixel_scale", real_space_width / n_pixels),
    )
    return n_pixels, pixel_scale, real_space_width


DEFAULT_KINMS_SOURCE_N_PIXELS = 256


def kinms_source_n_pixels_from_settings(settings):
    """Per-axis resolution of the phase-2 KinMS source grid."""
    return int(
        settings.get("source_grid", {}).get(
            "n_pixels", DEFAULT_KINMS_SOURCE_N_PIXELS
        )
    )


def kinms_source_grid_3d_from_settings(settings, n_channels: int) -> Grid3D:
    """
    Build the KinMS source-plane ``Grid3D``.

    If ``source_grid`` defines a bounding box (``bounding_box`` or
    ``xmin``/``xmax``/``ymin``/``ymax``), use :meth:`Grid3D.bounding_box`.
    Otherwise fall back to a uniform grid from :func:`source_grid_from_settings`.
    """
    source_cfg = settings.get("source_grid", {})
    bounding_box = source_grid_bounding_box_from_cfg(source_cfg)
    if bounding_box is not None:
        n_pixels = source_cfg.get("n_pixels")
        if n_pixels is None:
            raise ValueError(
                "source_grid bounding box requires 'n_pixels' (e.g. 512)."
            )
        return Grid3D.bounding_box(
            bounding_box=bounding_box,
            n_pixels=int(n_pixels),
            n_channels=n_channels,
        )

    n_pixels, pixel_scale, _ = source_grid_from_settings(settings)
    return Grid3D.uniform(
        n_pixels=n_pixels,
        pixel_scale=pixel_scale,
        n_channels=n_channels,
    )


def kinms_source_grid_3d(settings, n_channels: int, phase1_result=None) -> Grid3D:
    """
    KinMS source-plane grid for phase 2.

    **Parametric** (``phase1_result is None``): built from ``settings['source_grid']``
    — either a uniform field (``n_pixels`` + ``real_space_width``) or an explicit
    bounding box (``xmin``/``xmax``/``ymin``/``ymax`` + ``n_pixels``).

    **After phase 1** (``phase1_result`` set): the bounding box comes from the
    Autolens reconstruction mesh; only ``source_grid.n_pixels`` from settings sets
    the KinMS grid resolution.
    """
    if phase1_result is not None:
        from src.pipelines.reconstruction import phase2_source_grid_from_result

        return phase2_source_grid_from_result(
            result=phase1_result,
            n_channels=n_channels,
            settings=settings,
        )
    return kinms_source_grid_3d_from_settings(settings, n_channels=n_channels)


def source_grid_label_from_settings(settings, phase1_result=None):
    """Short human-readable description of the KinMS source grid."""
    if phase1_result is not None:
        from src.pipelines.reconstruction import source_plane_bounding_box_from_result

        y_min, y_max, x_min, x_max = source_plane_bounding_box_from_result(
            phase1_result
        )
        n_pixels = kinms_source_n_pixels_from_settings(settings)
        return (
            f"{n_pixels}² phase-1 bbox "
            f"x=[{x_min:.3f}, {x_max:.3f}]″ y=[{y_min:.3f}, {y_max:.3f}]″"
        )

    source_cfg = settings.get("source_grid", {})
    bounding_box = source_grid_bounding_box_from_cfg(source_cfg)
    if bounding_box is not None:
        y_min, y_max, x_min, x_max = bounding_box
        n_pixels = source_cfg.get("n_pixels", "?")
        return (
            f"{n_pixels}² bbox "
            f"x=[{x_min}, {x_max}]″ y=[{y_min}, {y_max}]″"
        )
    n_pixels, pixel_scale, width = source_grid_from_settings(settings)
    return f"{n_pixels}² ({width}″ field, {pixel_scale:.4g}″/pix)"


def image_plane_grid_from_settings(settings):
    """
    Image-plane grid for transformers, lensing evaluation, and dirty images.

    Always uses top-level ``n_pixels`` / ``real_space_width`` (not
    ``source_grid`` overrides).
    """
    n_pixels = settings["n_pixels"]
    real_space_width = settings["real_space_width"]
    pixel_scale = settings.get("pixel_scale", real_space_width / n_pixels)
    return n_pixels, pixel_scale, real_space_width


def image_plane_mask_from_settings(settings):
    n_pixels, pixel_scale, _ = image_plane_grid_from_settings(settings)
    return al.Mask2D.all_false(
        shape_native=(n_pixels, n_pixels),
        pixel_scales=pixel_scale,
    )


def image_extent_arcsec(real_space_width):
    half_width = real_space_width / 2.0
    return (-half_width, half_width, -half_width, half_width)


def image_extent_from_bounding_box(bounding_box):
    y_min, y_max, x_min, x_max = bounding_box
    return (x_min, x_max, y_min, y_max)


def nufftax_is_usable():
    """Return True if JAX-native nufftax NUFFT can be imported."""
    try:
        from src.utils.jax_compat import jax_is_usable, using_numpy_jax_stub

        if using_numpy_jax_stub() or not jax_is_usable():
            return False
    except Exception:
        return False
    try:
        import nufftax  # noqa: F401

        return True
    except Exception:
        return False


def default_transformer_class():
    """
    Prefer JAX-native ``TransformerNUFFT`` (nufftax) when available.

    Fallback order:
      1. ``TransformerNUFFT`` — real jax + nufftax
      2. ``TransformerNUFFTPyNUFFT`` — pynufft (no JAX)
      3. ``TransformerDFT`` — always available (slow for large UV sets)
    """
    if nufftax_is_usable():
        return al.TransformerNUFFT

    try:
        import pynufft  # noqa: F401

        return al.TransformerNUFFTPyNUFFT
    except Exception:
        return al.TransformerDFT


def transformer_class_from_settings(settings=None):
    """
    Resolve transformer class from settings.

    Optional keys (first match wins):
      - top-level ``transformer``
      - ``reconstruction.transformer``

    Values: ``auto`` (default), ``dft``, ``nufft`` / ``nufftax``, ``pynufft``.
    """
    name = None
    if settings is not None:
        name = settings.get("transformer")
        if name is None:
            name = settings.get("reconstruction", {}).get("transformer")
    if name is None or str(name).lower() in {"auto", "default"}:
        return default_transformer_class()

    key = str(name).lower()
    if key == "dft":
        return al.TransformerDFT
    if key in {"nufft", "nufftax"}:
        return al.TransformerNUFFT
    if key in {"pynufft", "nufft_pynufft"}:
        return al.TransformerNUFFTPyNUFFT
    raise ValueError(
        f"Unsupported transformer: {name!r}. "
        "Expected 'auto', 'dft', 'nufft'/'nufftax', or 'pynufft'."
    )


def transformer_class_with_primary_beam(base_class, primary_beam):
    """
    Return a callable with the ``(uv_wavelengths, real_space_mask)`` signature
    expected by ``al.Interferometer``, wrapping each instance in
    :class:`TransformerWithPrimaryBeam`.
    """
    def _factory(uv_wavelengths, real_space_mask, **kwargs):
        base = base_class(
            uv_wavelengths=uv_wavelengths,
            real_space_mask=real_space_mask,
            **kwargs,
        )
        return TransformerWithPrimaryBeam(base, primary_beam)
    _factory.__name__ = f"{base_class.__name__}+PB"
    return _factory


def transformer_from_uv_and_settings(
    uv_wavelengths,
    settings,
    transformer_class=None,
):
    if transformer_class is None:
        transformer_class = transformer_class_from_settings(settings)
    return transformer_class(
        uv_wavelengths=uv_wavelengths,
        real_space_mask=image_plane_mask_from_settings(settings),
    )


def dirty_image_from_visibilities(visibilities, uv_wavelengths, settings):
    """
    Dirty image on the settings image-plane grid (``n_pixels``, ``real_space_width``).
    """
    transformer = transformer_from_uv_and_settings(
        uv_wavelengths=uv_wavelengths,
        settings=settings,
    )
    if not isinstance(visibilities, al.Visibilities):
        visibilities = al.Visibilities(visibilities=visibilities)
    return array2d_to_numpy(
        transformer.image_from(visibilities=visibilities)
    )


class TransformerWithPrimaryBeam:
    """
    Thin wrapper that multiplies the real-space image by a primary-beam map
    before delegating to the underlying transformer.

    The adjoint (``image_from``) is *not* divided by the PB — dirty images
    remain in attenuated (observed) units, consistent with the data.
    """

    def __init__(self, base_transformer, primary_beam):
        self._base = base_transformer
        self._pb = primary_beam

    def __getattr__(self, name):
        return getattr(self._base, name)

    def visibilities_from(self, image, **kwargs):
        pb_image = al.Array2D(
            values=np.asarray(image) * self._pb,
            mask=self._base.real_space_mask,
        )
        return self._base.visibilities_from(image=pb_image, **kwargs)

    def image_from(self, visibilities, **kwargs):
        return self._base.image_from(visibilities=visibilities, **kwargs)


def transformers_from(
    uv_wavelengths,
    mask_3d: Mask3D,
    transformer_class=None,
    settings=None,
    primary_beam=None,
):
    if transformer_class is None:
        transformer_class = (
            transformer_class_from_settings(settings)
            if settings is not None
            else default_transformer_class()
        )

    transformers = []
    for i in range(mask_3d.n_channels):
        transformer = transformer_class(
            uv_wavelengths=uv_wavelengths[i],
            real_space_mask=mask_3d.mask_2d
        )
        if primary_beam is not None:
            transformer = TransformerWithPrimaryBeam(transformer, primary_beam)
        transformers.append(transformer)

    return transformers


def visibilities_from_transformers_and_cube(
    cube: np.ndarray,
    transformers: list,
    shape,
    z_mask=None,
    primary_beam=None,
):
    """
    Forward-model an image cube to visibilities via per-channel transformers.

    Parameters
    ----------
    primary_beam : ndarray (N, N), optional
        If supplied, each channel image is multiplied by this map before the
        Fourier transform (Gaussian antenna response / primary beam).
    """
    if z_mask is None:
        pass

    visibilities = np.zeros(shape=shape)
    for i, transformer in enumerate(transformers):
        if transformer is not None:
            channel = cube[i]
            if primary_beam is not None:
                channel = channel * primary_beam
            image = al.Array2D(
                values=channel,
                mask=transformer.real_space_mask,
            )
            visibilities_i = transformer.visibilities_from(image=image)
            vis_array = visibilities_i.array
            visibilities[i, :, 0] = vis_array.real
            visibilities[i, :, 1] = vis_array.imag
        else:
            raise NotImplementedError()

    return visibilities


def array2d_to_numpy(array_2d):
    """Convert an autoarray ``Array2D`` (or native view) to a plain 2D ndarray."""
    if hasattr(array_2d, "native"):
        array_2d = array_2d.native
    return np.asarray(getattr(array_2d, "array", array_2d))


def dirty_cube_from(
    visibilities: np.ndarray,
    transformers: list
):
    """
    Generate an image cube from visibilities.

    Notes
    -----
    `autolens` transformer APIs expect a visibilities object with a `.array`
    attribute (e.g. `al.Visibilities`), not a raw complex `numpy.ndarray`.

    Returned arrays use autolens image orientation and should be plotted with
    ``origin="lower"``.
    """

    return np.array([
        array2d_to_numpy(
            transformer.image_from(
                visibilities=al.Visibilities(
                    visibilities=visibilities[i, :, 0] + 1j * visibilities[i, :, 1]
                )
            )
        )
        for i, transformer in enumerate(transformers)
    ])


def dirty_noise_cube_from(
    noise_map: np.ndarray,
    transformers: list,
    *,
    n_realizations: int = 8,
    seed: int = 0,
):
    """
    Monte-Carlo estimate of the dirty-image noise cube from visibility σ.

    Draws ``n_realizations`` Gaussian noise visibility cubes
    ``N(0, noise_map)``, dirty-images each, and returns the per-pixel RMS
    over realizations (same shape as :func:`dirty_cube_from`).
    """
    sigma = np.asarray(noise_map, dtype=float)
    rng = np.random.RandomState(int(seed))
    acc = None
    n_realizations = max(int(n_realizations), 1)
    for _ in range(n_realizations):
        noise = rng.normal(size=sigma.shape) * sigma
        dirty = np.asarray(dirty_cube_from(noise, transformers), dtype=float)
        if acc is None:
            acc = dirty**2
        else:
            acc += dirty**2
    return np.sqrt(acc / float(n_realizations))


def dirty_mom0_noise_from_channel_noise(channel_noise_cube, z_step_kms):
    """
    Propagate per-channel dirty σ to mom0 = Σ_c dirty_c * dv (independent channels).

    ``σ_mom0 = dv * sqrt(Σ_c σ_c²)``.
    """
    sigma = np.asarray(channel_noise_cube, dtype=float)
    dv = float(z_step_kms)
    return dv * np.sqrt(np.sum(sigma**2, axis=0))
