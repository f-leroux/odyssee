# L’Odyssée — lecteur annoté

Lecteur web de **L’Odyssée** d’Homère, dans la traduction de Charles-René-Marie Leconte de L’Isle. Le texte a été extrait du PDF fourni puis restructuré par page imprimée et par chant.

## Lancer le site

```bash
python3 server.py
```

Ouvrir ensuite [http://localhost:8000](http://localhost:8000).

Le site propose les mêmes fonctions principales que le lecteur Moby Dick :

- navigation page par page, en haut et en bas ;
- accès direct à chacun des 24 chants ;
- accès direct à une page imprimée (4 à 347) ;
- reprise automatique à la dernière page lue ;
- annotation cliquable, mise en évidence dans le texte ;
- navigation au clavier avec les flèches gauche et droite.

Le texte contient **298 annotations distinctes** réparties dans les 24 chants : personnages et lieux, patronymiques et formes grecques choisies par Leconte de L’Isle, coutumes, religion, épithètes homériques et éclairages sur les principales scènes du récit. Une entrée de glossaire n’est affichée qu’à sa première occurrence pertinente dans tout le livre ; elle n’est pas répétée à chaque chant. Certaines pages peuvent donc être plus denses que d’autres.

## Régénérer le texte

Le script `tools/extract_odyssee.py` permet de recréer `text_data/Odyssee.json` à partir du PDF :

```bash
python3 tools/extract_odyssee.py "/chemin/vers/Homère_Odyssee.pdf" text_data/Odyssee.json
```

L’extraction recrée le texte brut avec l’annotation initiale. Pour reconstruire ensuite l’ensemble de l’appareil de notes :

```bash
python3 tools/annotate_odyssee.py text_data/Odyssee.json text_data/Odyssee.json
```

Le script d’annotation est idempotent : on peut le relancer sans dupliquer les marqueurs.
