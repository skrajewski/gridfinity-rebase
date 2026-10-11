"""Vectorized binary STL I/O; no heavyweight mesh-processing imports."""

import os
import re
import struct
import tempfile
from pathlib import Path

import manifold3d as m
import numpy as np

from . import RebaseError

FACET = np.dtype(
    [("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attr", "<u2")]
)
VERTEX = re.compile(rb"^\s*vertex\s+([^\r\n]+)", re.MULTILINE | re.IGNORECASE)


def read_stl(path: str | Path) -> m.Manifold:
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RebaseError(f"Cannot read {path}: {exc.strerror}") from exc
    count = struct.unpack_from("<I", data, 80)[0] if len(data) >= 84 else 0
    if count and len(data) == 84 + 50 * count:
        triangles = np.frombuffer(data, dtype=FACET, offset=84)["vertices"]
    elif data.lstrip().lower().startswith(b"solid"):
        rows = VERTEX.findall(data)
        try:
            vertices = np.array([row.split() for row in rows], dtype=np.float32)
        except ValueError as exc:
            raise RebaseError(f"{path}: malformed ASCII STL vertices") from exc
        facets = len(re.findall(rb"\bfacet\s+normal\b", data, re.IGNORECASE))
        if not facets or len(rows) != facets * 3 or vertices.shape != (len(rows), 3):
            raise RebaseError(f"{path}: incomplete ASCII STL facets")
        triangles = vertices.reshape(-1, 3, 3)
    else:
        raise RebaseError(f"{path}: empty, truncated or invalid STL")
    if not np.isfinite(triangles).all():
        raise RebaseError(f"{path}: STL contains NaN or infinite coordinates")
    # Native edge welding is faster than sorting every vertex with numpy.unique.
    vertices = np.ascontiguousarray(triangles.reshape(-1, 3))
    indices = np.arange(len(vertices), dtype=np.uint32).reshape(-1, 3)
    mesh = m.Mesh(vertices, indices)
    mesh.merge()
    solid = m.Manifold(mesh)
    if solid.status() != m.Error.NoError or solid.is_empty():
        raise RebaseError(
            f"{path}: STL is not a closed, consistently oriented solid ({solid.status().name})"
        )
    if solid.volume() <= 0:
        raise RebaseError(f"{path}: STL has inverted normals or non-positive volume")
    return solid


def write_stl(solid: m.Manifold, path: str | Path, *, overwrite: bool = False) -> int:
    """Publish a complete binary STL atomically; never truncate an existing file."""
    path = Path(path)
    # STL stores float32 coordinates. Quantizing near-coincident boolean
    # intersections can collapse tiny faces, so normalize at that precision
    # before writing, retaining the original topology/merge information.
    quantized = m.Manifold(solid.to_mesh())
    if quantized.status() != m.Error.NoError or quantized.is_empty():
        raise RebaseError("Cannot represent the result as a closed float32 STL")
    mesh = quantized.to_mesh()
    triangles = np.asarray(mesh.vert_properties)[:, :3][mesh.tri_verts]
    normals = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    lengths = np.linalg.norm(normals, axis=1)
    normals /= np.where(lengths > 0, lengths, 1)[:, None]
    records = np.zeros(len(triangles), dtype=FACET)
    records["vertices"] = triangles
    records["normal"] = normals
    if not len(records) or not np.isfinite(triangles).all():
        raise RebaseError("Cannot export an empty or non-finite mesh")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as out:
            temporary = Path(out.name)
            out.write(b"Gridfinity Rebase".ljust(80, b"\0"))
            out.write(struct.pack("<I", len(records)))
            out.write(records.tobytes())
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    except FileExistsError as exc:
        raise RebaseError(f"Output already exists: {path}; use --overwrite") from exc
    except OSError as exc:
        raise RebaseError(f"Cannot write {path}: {exc.strerror}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return len(records)
