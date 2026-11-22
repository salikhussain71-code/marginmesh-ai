# Security policy

MarginMesh AI is an early prototype. The optional HTTP API has **no authentication** and must
only be run locally. Do not upload real customer documents to any shared or public deployment.

To report a vulnerability, open a private security advisory on the GitHub repository (Security tab)
rather than a public issue.

Built-in protections: strict input validation, upload size/extension limits, server-chosen temp
file names, order-id allow-list (no path traversal), spreadsheet formula-injection neutralisation.
