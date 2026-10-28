# MatchLens Pocket Stadium

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <strong>Français</strong> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.ar.md">العربية</a>
</p>

**Voir MatchLens — la vidéo présente l’expérience hors ligne ; les agents connectés
à une API utilisent la même interface.**

https://github.com/user-attachments/assets/7c19dc86-b2b1-4d1c-8126-0246e06f65e4

<h3 align="center">
  <a href="https://yuxuanfuture.github.io/MatchLens/">▶ Ouvrir la démo interactive</a>
</h3>

<p align="center">Manipulez le Pocket Stadium présenté ci-dessus : replay, public, langue et disposition des panneaux. Aucun serveur ni clé API requis.</p>

[![CI](https://github.com/yuxuanfuture/MatchLens/actions/workflows/ci.yml/badge.svg)](https://github.com/yuxuanfuture/MatchLens/actions/workflows/ci.yml)

MatchLens transforme les événements de football observés en explications reliées à leurs preuves et en un stade miniature personnalisé. Les mêmes faits deviennent un récit concis pour les supporters, un contexte quantifié pour les analystes et des signaux synchronisés pour les incrustations de diffusion.

## Deux modes d’exécution

MatchLens est un framework exécutable de preuves et d’agents, pas seulement une démonstration vidéo prérendue.

| Mode | Ce qui s’exécute |
| --- | --- |
| **Hors ligne** | Traitement déterministe des événements, analyses, preuves, replay, localisation et interface. Aucun modèle ni clé API n’est requis. |
| **Multi-agent avec API** | DeepSeek ou un Ollama local pilote le Coordinator et les rôles spécialisés facultatifs ; les outils déterministes restent la source des faits numériques et un Verifier indépendant contrôle chaque proposition. |

Les deux modes partagent la même fenêtre d’observation figée, le même contrat de preuve, le Pocket Stadium et les contrôles de péremption. Un modèle peut enquêter et expliquer le match, mais il ne peut ni inventer des données, ni avancer l’horloge du replay, ni contourner le budget de requêtes.

## Pourquoi MatchLens

Les données de football sont faciles à compter mais difficiles à expliquer. MatchLens relie chaque affirmation aux événements ou aux données de suivi qui la justifient, respecte ce qui était observable à cet instant et expose l’incertitude au lieu de combler les lacunes par des faits inventés.

L’interface adapte un même flux de preuves aux modes Fan et Analyst. L’anglais est la langue par défaut ; le chinois simplifié, le français, l’espagnol et l’arabe sont également pris en charge, ainsi que le suivi d’une équipe ou d’un joueur, le Pocket Stadium rejouable et une incrustation de diffusion transparente.

## Points forts

- **Les preuves d’abord :** les explications renvoient aux données reçues et aux métriques déterministes ; une donnée manquante reste manquante au lieu de devenir zéro.
- **Conscient du replay :** le temps de l’événement et le temps d’arrivée sont séparés, afin qu’un replay ne révèle pas un but ou une décision VAR future.
- **Adapté au public :** les modes Fan et Analyst partagent les faits, mais diffèrent par le langage, la densité, le point de vue et la présentation.
- **Prêt pour le multi-agent :** un système borné facultatif peut déléguer l’enquête, vérifier indépendamment les affirmations et écarter les résultats obsolètes.
- **Démonstration portable :** l’expérience principale fonctionne avec Python et un navigateur moderne, sans étape de compilation front-end.

## Démarrage rapide : hors ligne

Prérequis : Python 3.13 et un navigateur moderne. Node.js 22 n’est nécessaire que pour les tests côté navigateur.

### macOS ou Linux

```bash
python3 -m backend.server --port 43128
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\start-matchlens-windows.ps1
```

Ouvrez <http://127.0.0.1:43128/?lang=fr>. Le service local doit rester actif, car il fournit le flux d’événements, les API de preuves et les commandes de replay.

## Connecter un fournisseur de modèle

Le dépôt comprend des adaptateurs pour l’API officielle DeepSeek et un service Ollama en boucle locale. La politique enregistrée échoue volontairement en mode fermé : l’ajout d’une clé ne déclenche donc aucune requête. Pour activer les enquêtes multi-agents avec API :

1. Configurez le fournisseur localement : conservez la clé DeepSeek dans `.env.local`, ignoré par Git, ou démarrez un modèle Ollama sur `127.0.0.1`.
2. Créez une autorisation explicite et bornée dans `config/model-policy.json`.
3. Démarrez le serveur pour les enquêtes continues regroupées par événements, ou exécutez `scripts/run_harness.py` sur un instantané figé du flux.

Consultez **[Configuration de l’API du modèle (en anglais)](docs/MODEL_API_SETUP.md)** pour les commandes DeepSeek et Ollama, les champs de politique, le fonctionnement des budgets et la désactivation. Les secrets n’entrent jamais dans le navigateur, les prompts, les traces ou les fichiers validés.

## Démonstration

Le scénario principal est une séquence de 120 secondes dans le temps additionnel : un tacle régulier lance une contre-attaque, un face-à-face est signalé hors-jeu, la VAR passe à une revue au bord du terrain et le but n’est accordé qu’une fois la décision finale observable.

Essayez de basculer entre les modes Fan et Analyst, de changer de langue, de suivre un joueur, d’ouvrir **See the evidence**, de générer un résumé et de revenir en arrière pour vérifier que les résultats futurs disparaissent.

## Système multi-agent

Le produit fonctionne sans modèle. Lorsque la politique fail-closed est explicitement activée, les mêmes outils de preuve figée peuvent être utilisés par un système d’enquête multi-agent borné :

![Architecture du système multi-agent MatchLens](docs/architecture/multi-agent-system-v3.svg)

Seul le Coordinator peut déléguer. Chaque proposition non vide reçoit une vérification indépendante, toutes les affirmations numériques doivent venir des outils déterministes et tout résultat lié à une ancienne position de lecture, préférence ou fenêtre de preuve est écarté. Les adaptateurs DeepSeek et Ollama local sont facultatifs ; la politique versionnée désactive les appels de modèle par défaut.

## Vérification

Lancez la suite complète d’acceptation hors ligne :

```bash
python3 scripts/offline_acceptance.py
```

Elle valide les données synthétiques, exécute les tests Python et les tests Node côté navigateur sans effectuer de requête vers une API de modèle. GitHub Actions suit le même parcours à chaque push et pull request.

## Structure du projet

| Chemin | Rôle |
| --- | --- |
| `backend/` | Service d’événements, analyses déterministes, outils de preuve, harness d’agents facultatif et traitements vidéo locaux |
| `dist/` | Pocket Stadium, moteur de rendu, localisation, outils de données et incrustation de diffusion |
| `data/` | Flux synthétiques reproductibles, manifestes et plans de signaux audio |
| `evals/` | Résultats attendus des fixtures et exécutions historiques clairement identifiées |
| `scripts/` | Génération de données, validation, configuration de l’environnement et commandes d’acceptation |
| `tests/` | Tests de régression Python et côté navigateur |
| `docs/` et `case-design/` | Contrats d’ingénierie, guides de configuration, limites et justification des scénarios |

## Documentation

- [Conception multi-agent](docs/HARNESS_PLAN.zh-CN.md)
- [Configuration de l’API du modèle (anglais)](docs/MODEL_API_SETUP.md)
- [Flux d’événements et incrustation](docs/STREAM_AND_OVERLAY.md)
- [Contrat des données synthétiques](data/README.md)
- [Guide d’acceptation hors ligne](docs/OFFLINE_ACCEPTANCE.zh-CN.md)
- [Inférence vidéo locale facultative](docs/WINDOWS_VIDEO.zh-CN.md)
- [Limites d’ingénierie](docs/ENGINEERING_ACCEPTANCE.zh-CN.md)
- [Présentation de la soumission](SUBMISSION.md)
- [Mentions relatives aux tiers](THIRD_PARTY_NOTICES.md)

## Limites et licence

- Tous les clubs, joueurs, événements, positions et scores sont des données synthétiques fictives.
- Aucun extrait de Premier League, flux de données officiel, écusson de club ou partenariat de production n’est inclus ni revendiqué.
- Le parcours vidéo facultatif est un prétraitement hors ligne, et non une démonstration d’inférence de diffusion en temps réel ; les pistes anonymes doivent être explicitement associées à un effectif.
- Le dépôt public exclut les poids de modèles, les enregistrements source tiers, la bande-son de foule générée et les environnements virtuels propres à une machine.

Le code original de MatchLens est disponible pour inspection, évaluation et test dans le cadre du hackathon selon la [LICENSE](LICENSE) source-available du dépôt. Les composants tiers restent soumis à leurs propres licences.
