# Backlog

Idées volontairement écartées de la v1, pour ne pas dériver du périmètre (§3.2 du cahier des charges).
Chaque entrée dit ce que c'est, pourquoi ce n'est pas dans la v1, et sous quelle condition ça y entrerait.

## Météo

- **Climatologie sur une fenêtre ±3 jours** au lieu d'un seul jour calendaire par année.
  5 échantillons (un par an) donnent une moyenne fragile ; une fenêtre de ±3 jours en donnerait 15,
  nettement plus robuste statistiquement.
  → v2, si le manque de robustesse devient visible en démo.

- **Agrégation restreinte aux heures effectivement courues** plutôt qu'à la journée entière.
  Une course qui part à 5 h du matin ne verra jamais le pic de température de 15 h ; l'agrégation
  actuelle sur 24 h peut donc surestimer la chaleur perçue.
  → v2, dépend du plan d'allure (F5) pour connaître l'heure de passage par segment.

## Segmentation

- **Segmentation par rupture de pente** (`slope_break`) avec fusion des segments courts,
  au lieu du pas fixe actuel.
  → reporté explicitement par le cahier des charges (F2), pas une improvisation de ma part.

## Plan d'allure

- **Vitesse ascensionnelle affichée sur tous les segments**, y compris les descentes.
  Ce n'est pas faux (un segment en descente nette contient quand même du D+ sur ses bosses),
  mais ce n'est pas actionnable pour le coureur.
  → v2, masquer la colonne hors segments de type montée.

- **Répartition de la nutrition sur les ravitaillements réels** (F6 le prévoit).
  Demande de détecter ou saisir les points de ravitaillement ; aujourd'hui le plan est
  purement horaire.
  → v2.

## Infrastructure

- **Images Docker séparées pour `api` et `ui`** : aujourd'hui `ui` réutilise l'image de
  l'API, qui embarque LangGraph et les dépendances de calcul dont Streamlit n'a pas besoin.
  → v2, gain marginal pour un projet portfolio.

- **Migration de `google.generativeai` vers `google.genai`** : la bibliothèque actuelle
  émet un `FutureWarning` de fin de support.
  → à faire quand `langchain-google-genai` aura basculé.

## Divers

- Connecteur Strava via MCP officiel, si Strava ouvre un jour un mode compatible usage tiers.
- Multi-agents spécialisés (parcours / physiologie / nutrition) coordonnés par un superviseur.
- Comparaison de scénarios de course (conservateur / agressif).
- Évaluation systématique sur un jeu de courses passées (plan prédit vs temps réel).
