# VideoAssembler — Montage automatique

Éditeur vidéo desktop Python/PyQt6 qui scanne un dossier, trie les clips par date EXIF et les assemble en un film avec transitions.

## Prérequis système

| Dépendance | Installation |
|---|---|
| Python 3.11+ | [python.org](https://python.org) |
| FFmpeg | `sudo apt install ffmpeg` / `brew install ffmpeg` / [ffmpeg.org](https://ffmpeg.org) |
| VLC *(aperçu)* | `sudo apt install vlc` / [videolan.org](https://www.videolan.org) |

## Installation

```bash
# Cloner / extraire le projet
cd video-editor

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate

# Installer les dépendances Python
pip install -r requirements.txt
```

## Lancement

```bash
python main.py
```

## Utilisation

### 1. Ouvrir un dossier
- **Fichier > Ouvrir dossier** ou bouton dans la barre d'outils
- Glisser-déposer un dossier directement sur la fenêtre
- Les vidéos sont scannées en arrière-plan, triées par date EXIF

### 2. Bibliothèque (panneau gauche)
- Tri par **Date EXIF**, **Nom** ou **Durée** via la liste déroulante
- Badge `[EXIF OK]` ou `[Date fichier]` indique la source de la date
- Glisser un clip vers la timeline pour l'ajouter

### 3. Timeline (centre bas)
- Glisser les vignettes pour **réordonner**
- `Delete` pour supprimer le clip sélectionné
- `Ctrl+Z` pour annuler le dernier réordonnancement
- `⚠` indique deux clips avec la même date EXIF (doublon probable)

### 4. Aperçu (centre haut)
- Cliquer sur un clip dans la timeline lance l'aperçu VLC
- `Espace` : play / pause

### 5. Transitions
- Choisir la transition globale dans la barre d'outils
- Régler la durée (0.1 s – 3.0 s)
- Transitions disponibles : Aucune · Fondu noir · Fondu enchaîné · Glissement gauche/droite · Zoom

### 6. Export
- **Fichier > Exporter le film** (`Ctrl+E`)
- Choisir résolution (720p / 1080p / 4K / originale), FPS, qualité
- La progression s'affiche en temps réel (parsing FFmpeg)

### 7. Projet
- **Fichier > Sauvegarder projet** (`Ctrl+S`) → fichier `.vap` (JSON)
- **Fichier > Ouvrir projet** (`Ctrl+P`) → restaure clips + paramètres

## Raccourcis clavier

| Raccourci | Action |
|---|---|
| `Ctrl+O` | Ouvrir dossier |
| `Ctrl+S` | Sauvegarder projet |
| `Ctrl+P` | Ouvrir projet |
| `Ctrl+E` | Exporter |
| `Ctrl+Z` | Annuler réordonnancement |
| `Espace`  | Play / Pause aperçu |
| `Delete`  | Supprimer clip sélectionné |
| `Ctrl+Q` | Quitter |

## Structure du projet

```
video-editor/
├── main.py                  # Point d'entrée
├── requirements.txt
├── CLAUDE.md
├── README.md
├── core/
│   ├── video_scanner.py     # Scan EXIF, thumbnails, VideoClip
│   ├── transitions.py       # 6 transitions + EffectProcessor
│   ├── video_editor.py      # Assemblage MoviePy + export FFmpeg
│   └── project.py           # Sauvegarde/restauration .vap
├── ui/
│   ├── main_window.py       # Fenêtre principale
│   ├── library_panel.py     # Panneau bibliothèque
│   ├── timeline.py          # Timeline drag & drop
│   └── style.py             # Thème sombre QSS
└── assets/
    └── thumbnails/          # Cache des vignettes
```
