# Contributing to EvoCall Assistant

Thank you for helping make the prototype easier to understand and test.

## Start small

Check existing issues or open a discussion before a substantial change. Describe the concrete behavior you want to improve and how someone can reproduce it. Useful contributions include documentation, accessibility, Windows WASAPI compatibility, and measured performance improvements.

## Local development

Use Python 3.12 with Tkinter for the supplied Windows launchers. The core and lifecycle tests run with the standard library; NumPy is optional for the simulated silent-input test.

```sh
python -m unittest discover -s tests -v
```

Do not start microphone capture or model downloads as part of automated tests. Use simulated devices and a loopback test server. Test the real Windows interface or devices separately and report exactly which checks you completed.

## Pull requests

- Explain the problem, resulting behavior, and relevant verification.
- Keep one coherent change per pull request.
- Add meaningful tests when behavior changes; preserve existing passing tests.
- Use synthetic conversations and example addresses such as `person@example.com`.
- Keep credentials, model files, recordings, transcripts, private logs, and machine-specific paths out of commits.
- Preserve the distinction between fixed demo rules and model-generated suggestions.

The current UI and prompts are in Italian. English is welcome for issues and development documentation.

## Privacy reports

For a report that could expose conversation data or credentials, use GitHub's private vulnerability reporting when available. Otherwise contact the maintainer through their GitHub profile to agree on a private channel before sending sensitive details. Do not publish personal data in an issue.

## License

Unless you explicitly state otherwise, contributions submitted for inclusion are under Apache-2.0, as described in [LICENSE](LICENSE). Do not submit code or assets that you cannot license compatibly. External libraries and models retain their own terms.
