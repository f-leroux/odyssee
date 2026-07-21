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

Le texte contient **299 annotations distinctes** réparties dans les 24 chants : personnages et lieux, patronymiques et formes grecques choisies par Leconte de L’Isle, coutumes, religion, épithètes homériques et éclairages sur les principales scènes du récit. Une entrée de glossaire n’est affichée qu’à sa première occurrence pertinente dans tout le livre ; elle n’est pas répétée à chaque chant. Certaines pages peuvent donc être plus denses que d’autres.

Deux annotations comportent une carte agrandissable : le choix de route de Nestôr entre Lesbos, Khios, Psyriè, Mimas et Géraistos au chant III, puis une reconstruction historique et explicitement conjecturale des errances d’Odysseus au début du chant IX.

## Régénérer le texte

Le script `tools/extract_odyssee.py` permet de recréer `text_data/Odyssee.json` à partir du PDF :

```bash
python3 tools/extract_odyssee.py "/chemin/vers/Homère_Odyssee.pdf" text_data/Odyssee.json
```

L’extraction recrée le texte brut avec l’annotation initiale. Pour reconstruire ensuite l’ensemble de l’appareil de notes :

```bash
python3 tools/annotate_odyssee.py text_data/Odyssee.json text_data/Odyssee.json
```

Le script d’extraction conserve les traits d’union lexicaux placés en fin de ligne dans le PDF (`très-malheureux`, `peut-être`, `dis-moi`, etc.). Le script d’annotation est idempotent : on peut le relancer sans dupliquer les marqueurs.

La carte détaillée du chant III est un schéma original fondé sur les positions relatives des îles et sur les identifications de [Mimas](https://www.perseus.tufts.edu/hopper/text?doc=Perseus%3Atext%3A1999.04.0064%3Aentry%3Dmimas-geo) et de [Géraistos](https://topostext.org/place/380245HGer). La carte générale des voyages est tirée de la traduction de Samuel Butler (1900), dans le domaine public, via [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Odyssey_(Butler)_Map.png). Elle est présentée comme une hypothèse historique parmi d’autres, puisque la géographie des épisodes merveilleux ne peut pas être établie avec certitude.
