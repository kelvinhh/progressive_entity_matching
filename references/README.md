# Reference materials

These are reference inputs, separate from the independent implementation in `src/pem/`.

| Local path | Source / purpose |
| --- | --- |
| `papers/3709715.pdf` | Maciejewski et al., *Progressive Entity Matching: A Design Space Exploration*, PACMMOD 3(1), Article 65, SIGMOD 2025. [DOI](https://doi.org/10.1145/3709715). |
| `papers/3709715_readme.pdf` | PDF copy of the authors' repository instructions; not a separate research paper. |
| `upstream/PER-Design-Space-Exploration-main/` | User-provided archive of the [authors' repository](https://github.com/JacobMaciejewski/PER-Design-Space-Exploration). Contains experiment drivers, configurations, figures, and published results. |

The original archive is preserved unchanged. Its commit/version is unknown. Its
core workflow drivers import `pyjedai`; the archive alone is not a standalone
implementation of every algorithm. Original result files and figures must not
be presented as outputs of our implementation.

PDFs and the upstream archive are ignored by Git. A fresh clone can obtain the
references from the links above; running our implementation does not require
these local archives. We have not copied upstream source code into `src/` and
have not assigned a license to the upstream materials.
