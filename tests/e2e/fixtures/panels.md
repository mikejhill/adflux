# Panel Macro Coverage

Confluence panels are ADF-only macros. adflux renders them in Markdown
as **GitHub-style alerts**, so the same Markdown source round-trips
through ADF without losing the panel type.

## Info panel

> [!NOTE]
>
> This is an **info** panel. It supports inline formatting like *italic*
> and `code`.

## Note panel

> [!IMPORTANT]
>
> A note panel for general advisory content.

## Warning panel

> [!WARNING]
>
> A warning panel --- use sparingly for things that need user attention.

## Success panel

> [!TIP]
>
> A success panel celebrates a positive outcome.

## Error panel

> [!CAUTION]
>
> An error panel highlights a failure or critical issue.

## Mixed content inside a panel

> [!NOTE]
>
> Panels can contain richer content:
>
> - bullet
> - list
>
> ```bash
> echo "even code blocks work"
> ```
