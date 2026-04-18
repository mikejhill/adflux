"""End-to-end tests against a live Confluence Cloud site.

These tests round-trip Markdown fixtures through adflux and Confluence:

    Markdown source
        → adflux MD→ADF
            → POST /wiki/api/v2/pages
                → GET  /wiki/api/v2/pages/{id}?body-format=atlas_doc_format
                    → adflux ADF→MD
                        → semantic comparison vs. original Markdown

The whole module is skipped automatically if `.env` (at the project root) is missing
required keys or if the credentials cannot authenticate against the
configured site.
"""
