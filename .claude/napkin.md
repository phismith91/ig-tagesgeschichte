# heute.today — Napkin

Kuratierte Runbook-Notizen für wiederkehrende Entscheidungen und langfristige Ideen.

## Growth & Content-Strategie

1. **Internationale Expansion (Idee)**
   - Hauptkanal `heute.today` könnte langfristig komplett englisch werden, um größere Reichweite zu erreichen.
   - Deutscher Content würde auf einen separaten Kanal ausgelagert, z. B. `heute.today.de` oder `heute.today.ger`.
   - Englischer Kanal ggf. `heute.today.en` oder einfach der Hauptkanal auf Englisch.
   - Noch nicht umsetzen — erst wachsen lassen, dann entscheiden.

2. **Hashtags**
   - Aktuell 4 Hashtags in der Caption. Reduzieren, wenn sie spammy wirken.
   - Favorit: `#geschichte #onthisday #wissen`

## Design

1. **Branding**
   - Markenname „heute.today" sollte auf jeder Slide sichtbar und gut lesbar sein.
   - Follower-CTA nur auf der letzten Slide.

## Tech

1. **Render-Pipeline**
   - Fonts laden nur, wenn die temporäre HTML im `templates/`-Verzeichnis gerendert wird (Font-Pfade relativ).
   - Temporäre HTML-Dateien werden nach dem Screenshot wieder aufgeräumt.
