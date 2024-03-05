# Changelog


## v3.3.1 (2024-03-05)

* Update readme.

* Add error for raw YUV files.

* Remove deprecated methods.


## v3.3.0 (2023-07-18)

* Add dist-delay option.

* Add encoding to setup.py for windows compat.

* Add encoding to setup.py for windows compat.


## v3.2.1 (2023-03-06)

* Check for existing files before running.

* Fix executable name in CLI help, again.


## v3.2.0 (2023-03-06)

* Allow overriding temp dir.

* Fix executable name in CLI help.

* Link to VMAF docs.

* Fix formatting.

* Update README with more features.

* Add warning for same file input, fixes #59.

* Update contributors.


## v3.1.7 (2023-02-20)

* Fix readme example, fixes #58.


## v3.1.6 (2023-02-19)

* Update README and docs.

* Remove stalebot.

* Update README.


## v3.1.5 (2023-01-04)

* Fix keep-tmp option.

* Update docker instructions.

* Fix github workflows.

* Add workflow badge.

* Update python metadata, remove old console script.

* Minor code formatting.

* Add github workflows.

* Fix type error.


## v3.1.4 (2023-01-03)

* Remove MANIFEST.in.

* Fix API import.

* Sort imports.


## v3.1.3 (2022-12-23)

* Fix finding version in setup.py.


## v3.1.2 (2022-12-23)

* Format with black.

* Improve types.


## v3.1.1 (2022-12-18)

* Improve typing support.

* Add contributor manually.

* Docs: update .all-contributorsrc [skip ci]

* Docs: update README.md [skip ci]

* Docs: update .all-contributorsrc [skip ci]

* Docs: update README.md [skip ci]

* Docs: create .all-contributorsrc [skip ci]

* Docs: update README.md [skip ci]

* Add contributors template.


## v3.1.0 (2022-12-11)

* Fix VMAF model path error on Windows, fixes #42.

* Fix flaky tests.

* Fix AVTB setting, see #39.

* Fix default docker image name.

* Fix docs link.

* Add explicit return type for calculate() function.

* Decrease max width of args, update README.

* Update tests.


## v3.0.0 (2022-08-08)

* Support for VMAF 2.0 only.

* Update copyright.

* Remove warning for libvmaf in johnvansickle builds.

* Use latest linux build instead of release builds.


## v2.3.0 (2021-12-22)

* Update docs.

* Update README.

* Remove unneeded warning.

* Print stdout on error to help with debugging.

* Reomve underline from log.

* Add better logging capabilities.

* Normalize time base for comparison.

  see https://trac.ffmpeg.org/ticket/9560

* Fix default model path selection for VMAF.

* Update test vector values.

* Filter out LICENSE in model path.


## v2.2.0 (2021-05-31)

* Fix detection of libvmaf model dir, fixes #34.

* Re-add old PKL models.

* Make docker a bit more quiet.


## v2.1.0 (2021-05-27)

* Add option to keep temporary files.

* Always pick latest dockerfile version for docker_run script.

* Improve dockerfile build.

* Create FUNDING.yml.

* Update badge link.


## v2.0.3 (2021-03-10)

* Add python_requires to setup.py.


## v2.0.2 (2021-03-10)

* Fix README.


## v2.0.1 (2021-03-10)

* Fix README.


## v2.0.0 (2021-03-10)

* Change CLI syntax, add VIF filter.

  Move CLI syntax to a more flexible format for selecting metrics.
  This is not backwards-compatible, so a major release.
  Add the VIF filter.

* Fix bug if VMAF is the only metric.

* Update docs.


## v1.2.0 (2021-03-10)

* Update docs.

* Deprecate old API.

* Add single calc() function, fixes #32.

* Add dev requirements.

* Explicitly call VMAF model in test.

* Support Python 3.9.

* Fix flake8 errors.

* Simplify VMAF function.

* Detect available filters.

* Note how to update docs.

* Update docs.

* Remove release script.


## v1.1.3 (2021-03-06)

* Update ffmpeg-progress-yield requirement.

* Format setup.py.


## v1.1.2 (2021-03-06)

* Add missing CLI option to readme.


## v1.1.1 (2021-03-06)

* Fix long description content type.


## v1.1.0 (2021-03-06)

* Add progress bar, fixes #12.

* Add vscode to gitignore.

* Add VMAF unit test.

* Improve README.


## v1.0.1 (2021-03-01)

* Fix setup.py file.


## v1.0.0 (2021-03-01)

* Allow top-level import.

* Update badge URL.


## v0.12.1 (2021-02-12)

* Update changelog format, release script.

* Fix docs link, again.


## v0.12.0 (2021-02-12)

* Improve VMAF model selection, fixes #30.


## v0.11.1 (2021-02-11)

* Fix readme.

* Fix docs link.


## v0.11.0 (2021-02-11)

* Add API docs.

* Convert into library, fixes #29.


## v0.10.0 (2021-02-10)

* Do not freeze pandas requirement, it does not matter.

* Improve help output from docker_run.sh.

* Update Dockerfile to use static build.


## v0.9.0 (2021-02-09)

* Add a note for Homebrew users.

* Fix possibly unbound variables.

* Remove unused variable.

* Improve default model file lookup; minor style fixes.

* [libvmaf] use vmaf_models/vmaf_v0.6.1.json by default.

* Include the model files.

* Add model files.

* Detect whether used ffmpeg is from Homebrew.

* Add placeholder and instructions for model path, addresses #19.

* Change n_threads to int, minor fixes.

* Remove program name.

* Remove a duplicate line.

* No need to include the default value in the help msg as ArgumentDefaultsHelpFormatter takes care of this.

* Add option to set the value of libvmaf's n_threads option.


## v0.8.0 (2021-01-22)

* Document threads option.

* Change default threads to 0.

* Added option for selecting number of threads (#26)

  * Added option for selecting number of threads

  * convert threads to str

  * change default threads CLI arg to int


## v0.7.1 (2021-01-09)

* Remove color support.

* Merge pull request #24 from slhck/fix-windows-paths.

  fix Windows paths, fixes #23

* Fix Windows paths, fixes #23.


## v0.7.0 (2021-01-07)

* Do not try to convert while getting fps, addresses #22.

* Add colorama support for Windows ANSI escapes, fixes #21.

* Properly handle dry run, fixes #20.


## v0.6.2 (2020-10-22)

* Update readme, fixes #18.


## v0.6.1 (2020-10-01)

* Merge pull request #16 from dpasqualin/issue_15.

  Closes #15: fix 'print_stderr' is not defined

* Closes #15: fix 'print_stderr' is not defined.

* Improve readme.


## v0.6.0 (2020-07-21)

* Improve warnings and messages, add -r parameter.


## v0.5.1 (2020-07-21)

* Merge pull request #14 from BassThatHertz/master.

  Prevent users on Windows from seeing an "UnboundLocalError"

* Add sys.exit(1) to prevent users on Windows from seeing "UnboundLocalError: local variable 'model_path' referenced before assignment"


## v0.5.0 (2020-07-21)

* Set PTS and framerate for input files.

* Apply black formatting.


## v0.4.0 (2020-07-17)

* Add global statistics, fixes #13.


## v0.3.12 (2020-07-15)

* Apply windows path modifications to VMAF model.


## v0.3.11 (2020-07-13)

* Update Dockerfile Homebrew tag.

* Update README.

* Show error if using Windows and VMAF, fixes #10.

* Update test values, add almost equal comparison.

* Remove unused import.

* Remove unused import.


## v0.3.10 (2020-04-08)

* Show all commits in release.

* Check for brew before setting model path, fixes #9.


## v0.3.9 (2020-03-15)

* Update release script.

* Rename CHANGELOG.


## v0.3.8 (2020-03-15)

* Version bump to 0.3.8.

* Compatibility with python 3.8.


## v0.3.7 (2020-01-08)

* Version bump to 0.3.7.

* Change image to official homebrew/brew.

* Pin pandas.


## v0.3.6 (2019-10-15)

* Version bump to 0.3.6.

* Fix string.


## v0.3.5 (2019-09-09)

* Version bump to 0.3.5.

* Switch Homebrew tap.

* Fix Dockerfile.


## v0.3.4 (2019-06-07)

* Version bump to 0.3.4.

* Clarify instructions.

* Merge pull request #7 from cdgriffith/development.

  Windows fixes

* Fixing windows path issue for ffmpeg Fixing VMAF model automatic finding via brew broken for windows.


## v0.3.3 (2019-05-25)

* Version bump to 0.3.3.

* Add missing pandas dependency.

* Fix dockerfile entry point, fixes #4.


## v0.3.2 (2019-05-25)

* Version bump to 0.3.2.

* Fix python compatibility.

* Remove old python script.

* Update gitignore.

* Add PyPI badge.


## v0.3.1 (2019-05-25)

* Version bump to 0.3.1.

* Fix URL and description in setup file.


## v0.3 (2019-05-25)

* Version bump to 0.3.

* Make a package.


## v0.2 (2019-04-19)

* Version bump to 0.2.

* Add input file paths to output.

* Update README.md.

* Update readme.

  explain simple usage

* Update readme.


## v0.1.2 (2019-04-18)

* Version bump to 0.1.2.

* Simplify lookup of latest share path.

* Fix README.


## v0.1.1 (2019-04-15)

* Version bump to 0.1.1.

* Add initial version.


## v0.1.0 (2019-04-13)

* WIP: add VMAF.

* Fix entrypoint.

* Add Dockerfile.

* Fix program name.

* Return stdout/stderr.

* Error handling for empty data.

* Add verbose/dry flags.

* Add choice for scaling algos.

* Initial commit.


