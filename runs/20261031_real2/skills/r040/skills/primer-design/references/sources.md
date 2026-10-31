# Sources and maintenance notes

Checked 2026-10-01. Links below are upstream documentation or primary publications.
Their availability does not imply that remote services, specialized assays, or
every API option were exercised by the bundled test suite.

## Executable design and analysis

- [Primer3 manual]([url-1]): authoritative Boulder-IO design
  tags, coordinates, constraint semantics, and output definitions. Distinguish
  template binding length from products that include overhangs.
- [primer3-py documentation]([url-2]): documentation
  currently identifies release 2.3.1 and links the Primer3 2.6.1 manual. Package and
  embedded engine versions are distinct; record both at runtime.
- [Primary Python API]([url-3]):
  `design_primers`, Tm/structure functions, physical parameters, and length limits.
- [Thermodynamic result API]([url-4]):
  result units, structure flags, and `get_libprimer3_version`.
- [PyPI release metadata]([url-5]): current package
  release remains 2.3.1; the bundled pin is unchanged.

## Reference specificity

- [NCBI Primer-BLAST]([url-6]): current
  assay-design/specificity interface and field-level help.
- [NCBI search tips]([url-7]):
  accession-based inputs, target assignment, and search interpretation.
- [Ye et al. (2012), Primer-BLAST]([url-8]):
  combined design, alignment, and amplicon-level specificity workflow.
- [BLAST+ nucleotide options]([url-9]):
  short-query tasks and search settings. Consult the installed executable's help
  because the Bookshelf table also contains historical release information.

The local Python contract remains `design_primers(seq_args, global_args)` returning
a result dictionary, and snake_case thermodynamic functions returning a float Tm
or `ThermoResult`. BLAST screening invokes local `makeblastdb` and `blastn`, parsing
declared tabular fields; it has no network API/authentication requirement. The
Primer-BLAST website was read for database and mismatch-field semantics; no public
sequence was submitted and no undocumented request/response endpoint is supported.

## Thermodynamic foundations

- [SantaLucia (1998)]([url-10]): DNA nearest-neighbor
  parameter framework, DOI `10.1073/pnas.95.4.1460`.
- [Owczarzy et al. (2008)]([url-11]): mixed-ion
  corrections, DOI `10.1021/bi702363u`.
- [Owczarzy et al. (2011)]([url-12]): LNA-specific
  thermodynamics and mismatch behavior, DOI `10.1021/bi200904e`.

## Assay-specific evidence

- [Bustin et al. (2025), MIQE 2.0]([url-13]):
  current qPCR assay reporting and validation guidance,
  DOI `10.1093/clinchem/hvaf043`.
- [NEB overlap-assembly primer guidance]([url-14]):
  connecting annealing regions to assembly overlaps.
- [Brown et al., PrimerPooler]([url-15]): multiplex
  pool allocation; consult the linked erratum when reproducing published details.
- [Rose et al. (2003), CODEHOP]([url-16]):
  protein-alignment-guided degenerate primers, DOI `10.1093/nar/gkg524`.
- [Li and Dahiya (2002), MethPrimer]([url-17]):
  bisulfite-specific design constraints, DOI `10.1093/bioinformatics/18.11.1427`.
- [Tusnády et al. (2005), BiSearch]([url-18]):
  converted-reference mispriming analysis, DOI `10.1093/nar/gni012`.

## When maintaining this skill

Check upstream parameter names, supported alphabets/lengths, concentrations, output
coordinates, and returned warnings before changing package pins. Re-run the
repository suite and documented examples. Test off-target products and negative
cases, not only whether a program returns primers. Preserve the distinction between
locally tested numerical behavior, external service documentation, and empirical
assay validation. A newer package or web interface does not justify upgrading old
assay claims without rerunning their evidence.
