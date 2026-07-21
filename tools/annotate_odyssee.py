#!/usr/bin/env python3
"""Ajoute un appareil de notes homogène au JSON du lecteur de L'Odyssée.

Le script est idempotent : il retire d'abord les marqueurs existants, puis
reconstruit toutes les notes à partir du catalogue ci-dessous.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path


MARKER_RE = re.compile(r"\[\^\d+\]")


@dataclass(frozen=True)
class Rule:
    key: str
    terms: tuple[str, ...]
    body: str
    scope: str = "book"  # "book" ou "chant"


@dataclass(frozen=True)
class Event:
    chant: int
    anchor: str
    body: str


def rule(key: str, terms: str | tuple[str, ...], body: str, scope: str = "book") -> Rule:
    if isinstance(terms, str):
        terms = (terms,)
    return Rule(key, terms, body, scope)


# Les entrées de glossaire ne sont annotées qu'une fois dans tout le livre,
# à leur première occurrence pertinente. Les événements, eux, restent liés
# aux passages précis qu'ils éclairent.
GLOSSARY = [
    rule("odysseus", "Odysseus", "Nom grec d’Ulysse. Leconte de L’Isle conserve les formes grecques ; le héros se distingue par sa <em>mètis</em>, intelligence rusée et capacité d’adaptation."),
    rule("telemaque", "Tèlémakhos", "Télémaque, fils d’Odysseus et de Pènélopéia. Sa recherche du père est aussi un apprentissage de la parole publique et de l’autorité."),
    rule("penelope", "Pènélopéia", "Pénélope, épouse d’Odysseus. Sa fidélité n’est pas passive : par la parole, le tissage et les épreuves qu’elle impose, elle déploie une prudence comparable à celle de son mari."),
    rule("athena", ("Athènè", "Pallas", "Tritogénéia"), "Athéna, aussi appelée Pallas ou Tritogénéia, est la déesse de l’intelligence, de la stratégie et des savoir-faire. Protectrice d’Odysseus, elle agit souvent sous un déguisement plutôt que par une intervention ouverte."),
    rule("zeus", "Zeus", "Souverain des dieux et garant de l’ordre, des serments et de l’hospitalité. Dans le poème, ses décisions fixent le cadre dans lequel les autres dieux et les humains exercent leur liberté."),
    rule("poseidon", "Poseidaôn", "Poséidon, dieu de la mer et des séismes. Il poursuit Odysseus parce que celui-ci a aveuglé son fils, le Kyklôps Polyphèmos."),
    rule("helios", ("Hèlios Hypérionade", "Hèlios"), "Hélios, personnification du Soleil, est fils du Titan Hypériôn : « Hypérionade » signifie ici « descendant d’Hypériôn ». Son regard embrasse le monde et ses troupeaux sacrés de Thrinakiè ne doivent jamais être touchés."),
    rule("pretendants", ("Prétendants", "prétendants"), "Aristocrates d’Ithakè et des îles voisines qui pressent Pènélopéia de choisir un nouvel époux. Leur consommation abusive des biens d’Odysseus viole à la fois la maison royale et les règles de l’hospitalité."),
    rule("ithaque", "Ithakè", "Ithaque, île et royaume d’Odysseus. Plus qu’un territoire, elle représente dans le poème la maison, l’identité et le terme du <em>nostos</em>, le retour."),
    rule("akhaiens", "Akhaiens", "Les Achéens, nom collectif donné aux Grecs de l’âge héroïque. Homère emploie aussi les noms d’Argiens et de Danaens."),
    rule("eos", ("Éôs", "Eôs"), "Éos, l’Aurore personnifiée. Ses apparitions répétées rythment le récit ; « aux doigts rosés » est une épithète formulaire de la poésie orale."),
    rule("hyperion", "Hypériôn", "Hypérion, Titan associé à la lumière céleste et père de Hèlios dans la généalogie mythologique. Il ne faut pas le confondre avec son fils, le Soleil lui-même."),
    rule("agamemnonide", "Agamemnonide", "Patronymique signifiant « fils d’Agamemnôn ». Il désigne ici Orestès ; les patronymiques situent constamment les héros dans leur lignée."),
    rule("atreide", ("l'Atréide", "Atréide", "Atréides"), "« Atréide » signifie « fils d’Atrée ». Le titre peut désigner Agamemnôn ou Ménélaos selon le contexte ; ici, il s’agit d’Agamemnôn."),
    rule("kronide", ("Kronide", "Kroniôn"), "Patronymique de Zeus, fils de Kronos. Les formes « Kronide » et « Kroniôn » rappellent sa place dans la succession des générations divines."),
    rule("laertiade", "Laertiade", "Patronymique d’Odysseus : « fils de Laertès ». Cette manière de nommer un héros rattache son identité personnelle à sa maison et à ses ancêtres."),
    rule("peleide", ("Pèléide", "Pèlèiade", "Pèléiôn"), "Patronymique d’Akhilleus, fils de Pèleus. Leconte de L’Isle conserve ici plusieurs formes proches du grec homérique."),
    rule("nestoride", "Nestoride", "Patronymique signifiant « fils de Nestôr » ; dans ce passage, il désigne Peisistratos."),
    rule("tueur_argos", "tueur d'Argos", "Épithète d’Hermès : il tua Argos Panoptès, le gardien « qui voit tout », géant couvert d’yeux dans la tradition mythologique."),
    rule("argos", ("Hellas et Argos", "dans Argos", "Argos nourrice de chevaux"), "Argos est une cité et une région majeure du Péloponnèse. Dans l’épopée, son nom peut aussi désigner plus largement le pays des Achéens ; à ne pas confondre avec Argos Panoptès ni avec le chien d’Odysseus."),
    rule("atlas", "Atlas", "Atlas, Titan condamné à soutenir le ciel aux confins du monde. Kalypsô est présentée comme sa fille."),
    rule("apollon", ("Apollôn", "Apollon", "Phoibos", "Paièôn", "Paian"), "Apollon, aussi appelé Phoibos, est le dieu de l’arc, de la musique, de la prophétie et de la guérison. <em>Paian</em> ou Paièôn est un nom lié à sa fonction de dieu guérisseur."),
    rule("artemis", "Artémis", "Artémis, déesse de la chasse et sœur d’Apollôn. Les héroïnes sont souvent comparées à sa beauté et à sa haute stature."),
    rule("aphrodite", "Aphroditè", "Aphrodite, déesse du désir et de l’union amoureuse. Le poème montre aussi la puissance perturbatrice du désir qu’elle inspire."),
    rule("ares", "Arès", "Arès, dieu de la fureur guerrière. Il représente la violence du combat plus que la stratégie maîtrisée d’Athènè."),
    rule("hephaistos", "Hèphaistos", "Héphaïstos, dieu forgeron et artisan des dieux. Ses œuvres — armes, bijoux ou automates — donnent à la technique une puissance presque vivante."),
    rule("hera", "Hèrè", "Héra, épouse de Zeus et souveraine parmi les déesses. Les formules généalogiques et conjugales rappellent fréquemment son rang."),
    rule("hades", ("Aidès", "Aidés", "Hadès"), "Hadès désigne à la fois le dieu souverain des morts et, par extension, son domaine souterrain."),
    rule("persephone", "Perséphonéia", "Perséphone, épouse d’Aidès et reine des morts. La forme « Perséphonéia » suit la translittération archaïsante de Leconte de L’Isle."),
    rule("ouranos", "Ouranos", "Ouranos est le Ciel personnifié. Dans la langue épique, le mot désigne aussi simplement la voûte céleste où résident les dieux."),
    rule("okeanos", "Okéanos", "Océan est le fleuve cosmique qui entoure les terres habitées, plutôt que l’étendue marine appelée aujourd’hui océan."),
    rule("vents", ("Boréas", "Zéphyros", "Notos", "Euros"), "Les vents sont personnifiés et nommés par leur direction : Borée vient du nord, Zéphyr de l’ouest, Notos du sud et Euros de l’est."),
    rule("hermes", ("Herméias", "Hermès", "Kyllénien"), "Hermès, messager des dieux, protecteur des voyageurs et maître des passages. Il guide aussi les âmes des morts, fonction dite psychopompe ; « Kyllénien » rappelle sa naissance au mont Kyllène."),
    rule("calypso", "Kalypsô", "Calypso, nymphe d’Ogygiè dont le nom évoque l’action de cacher. Elle offre l’immortalité à Odysseus, mais le retient loin de son identité et de sa demeure."),
    rule("ogygie", "Ogygiè", "Ogygie, île lointaine de Kalypsô. Son emplacement indéterminé renforce son caractère de marge merveilleuse, hors du monde social."),
    rule("polyphème", "Polyphèmos", "Polyphème, Kyklôps fils de Poseidaôn. Son nom signifie approximativement « celui dont on parle beaucoup », ironie importante dans l’épisode où Odysseus se nomme « Personne »."),
    rule("circe", "Kirkè", "Circé, déesse magicienne de l’île d’Aiaiè. Dangereuse puis hospitalière, elle transforme les hommes et fournit à Odysseus les instructions nécessaires pour la suite du voyage."),
    rule("aiolos", "Aiolos", "Éole, gardien des vents dans cet épisode. Il ne faut pas le confondre systématiquement avec le dieu du vent des traditions plus tardives."),
    rule("teiresias", "Teirésias", "Tirésias, devin thébain. Même mort, il conserve sa clairvoyance et révèle à Odysseus les conditions de son retour ainsi que le voyage qui devra le suivre."),
    rule("sirènes", "Seirènes", "Les Sirènes attirent les navigateurs par un chant qui promet un savoir total. Leur danger tient moins à la beauté qu’à une connaissance qui immobilise et détourne du retour."),
    rule("scylla", ("Skyllè", "Skillè"), "Scylla, monstre à plusieurs gueules qui enlève les marins depuis sa caverne. Elle incarne un péril inévitable : le bon choix ne supprime pas la perte, il la limite."),
    rule("charybde", "Kharybdis", "Charybde, gouffre marin qui engloutit et rejette périodiquement les eaux. Avec Skyllè, elle forme l’alternative proverbiale entre deux dangers."),
    rule("alkinoos", "Alkinoos", "Alcinoos, roi des Phaiakiens. Son écoute transforme l’étranger naufragé en hôte reconnu et permet enfin l’organisation du retour."),
    rule("arete", "Arètè", "Arété, reine des Phaiakiens. Son autorité domestique et politique est exceptionnelle ; Nausikaa conseille à Odysseus de s’adresser d’abord à elle."),
    rule("nausicaa", "Nausikaa", "Nausicaa, fille d’Alkinoos et d’Arètè. Sa rencontre avec Odysseus combine hospitalité, éveil au mariage et maîtrise des convenances."),
    rule("demodocos", "Dèmodokos", "Démodocos, aède aveugle des Phaiakiens. Ses chants sur Troie provoquent les larmes d’Odysseus et font passer l’expérience vécue dans la mémoire collective."),
    rule("phaiakiens", "Phaiakiens", "Les Phéaciens, navigateurs fabuleux de Skhériè. Leur société idéale sert d’étape entre le monde merveilleux des errances et le retour politique à Ithakè."),
    rule("skherie", "Skhériè", "Schérie, pays des Phaiakiens. Cette terre d’abondance et de navigation parfaite constitue la dernière escale avant Ithakè."),
    rule("eumee", "Eumaios", "Eumée, porcher d’Odysseus. Bien qu’asservi, il est présenté comme un modèle de loyauté, de piété et d’hospitalité."),
    rule("euryclee", "Eurykléia", "Euryclée, vieille nourrice d’Odysseus puis de Tèlémakhos. Sa connaissance intime du corps et de la maison fait d’elle une figure essentielle de la reconnaissance."),
    rule("laerte", "Laertès", "Laërte, père âgé d’Odysseus. Retiré aux champs et accablé par le deuil, il représente la continuité fragile de la lignée royale."),
    rule("antinoos", "Antinoos", "Antinoos, le plus brutal des prétendants et le principal moteur de leurs violences. Il incarne l’abus de force sans respect des limites sociales ou religieuses."),
    rule("eurymachos", "Eurymakhos", "Eurymaque, prétendant habile à dissimuler son hostilité derrière des paroles conciliantes. Après Antinoos, il est le meneur le plus influent du groupe."),
    rule("amphinomos", "Amphinomos", "Amphinomos, prétendant plus mesuré que les autres. Sa modération ne suffit pourtant pas à le dégager de la faute collective ni du destin du groupe."),
    rule("melanthios", "Mélanthios", "Mélanthios, chevrier d’Odysseus passé au service des prétendants. Sa trahison domestique répond, en négatif, à la fidélité d’Eumaios et de Philoitios."),
    rule("philoitios", "Philoitios", "Philoetios, bouvier fidèle d’Odysseus. Avec Eumaios, il aide le maître revenu à reprendre sa maison."),
    rule("mentor", "Mentôr", "Mentor, ami auquel Odysseus a confié sa maison. Athènè emprunte fréquemment son apparence ; de là vient le sens moderne du mot « mentor »."),
    rule("mentes", "Mentès", "Mentès, roi des Taphiens et ancien hôte d’Odysseus. Athènè prend son apparence pour approcher Tèlémakhos au chant I."),
    rule("phemius", "Phèmios", "Phémios, aède contraint de chanter pour les prétendants. Son statut pose une question importante : l’artiste est-il responsable des maîtres qui l’obligent à les servir ?"),
    rule("medon", "Médôn", "Médon, héraut de la maison. Resté loyal à Pènélopéia et à Tèlémakhos, il sera distingué de la masse des serviteurs compromis."),
    rule("nestor", "Nestôr", "Nestor, vieux roi de Pylos et mémoire vivante de la guerre de Troie. Sa parole abondante transmet à Tèlémakhos les récits des retours grecs."),
    rule("pisistrate", "Peisistratos", "Pisistrate, fils de Nestôr. Il accompagne Tèlémakhos à Spartè et lui offre le modèle d’un jeune prince déjà intégré à une lignée stable."),
    rule("menelas", "Ménélaos", "Ménélas, roi de Sparte, frère d’Agamemnôn et époux d’Hélènè. Son propre retour long et détourné fournit un miroir partiel de celui d’Odysseus."),
    rule("helene", ("Hélénè", "Hélènè"), "Hélène, dont l’enlèvement ou la fuite avec Pâris provoqua la guerre de Troie. Dans l’<em>Odyssée</em>, elle est à la fois personnage, interprète et narratrice de cette mémoire."),
    rule("agamemnon", "Agamemnôn", "Agamemnon, chef de l’expédition achéenne, assassiné à son retour par Aigisthos avec la complicité de Klytaimnestrè. Son destin est le contre-modèle qui menace Odysseus."),
    rule("orestes", "Orestès", "Oreste, fils d’Agamemnôn, qui venge le meurtre de son père. Le poème le présente à plusieurs reprises comme exemple possible pour Tèlémakhos."),
    rule("aigisthos", "Aigisthos", "Égisthe, amant de Klytaimnestrè et meurtrier d’Agamemnôn. Zeus rappelle qu’il a choisi sa faute malgré un avertissement divin."),
    rule("clytemnestre", "Klytaimnestrè", "Clytemnestre, épouse d’Agamemnôn et complice de son meurtre. Son histoire sert de sombre contraste à celle de Pènélopéia."),
    rule("achille", "Akhilleus", "Achille, plus grand guerrier achéen de l’<em>Iliade</em>. Dans l’<em>Odyssée</em>, sa gloire héroïque est confrontée au prix irréversible de la mort."),
    rule("aias", "Aias", "Ajax, héros achéen. Son retour échoue lorsqu’il se vante d’avoir échappé à la mer contre la volonté des dieux."),
    rule("elpenor", "Elpènôr", "Elpénor, jeune compagnon mort accidentellement chez Kirkè. Sa demande de sépulture rappelle qu’aucun retour ne peut réussir en négligeant les devoirs envers les morts."),
    rule("euryloque", "Eurylokhos", "Euryloque, parent et second d’Odysseus. Sa prudence est parfois lucide, mais il mène aussi la révolte qui aboutit au sacrifice des troupeaux de Hèlios."),
    rule("anticlee", "Antikléia", "Anticlée, mère d’Odysseus. Sa rencontre au pays des morts donne au héros des nouvelles de sa famille et mesure le coût affectif de son absence."),
    rule("ino", "Inô", "Ino, mortelle divinisée sous le nom marin de Leukothéè. Le voile qu’elle prête à Odysseus lui permet de survivre au naufrage."),
    rule("protee", "Prôteus", "Protée, « Vieillard de la mer », prophète capable de changer de forme. Il ne livre son savoir qu’à celui qui sait le retenir à travers ses métamorphoses."),
    rule("eidothee", "Eidothéè", "Eidothée, fille de Prôteus. Comme plusieurs figures féminines du poème, elle fournit au héros l’instruction pratique qui rend possible l’accès au savoir."),
    rule("autolycos", "Autolykos", "Autolycos, grand-père maternel d’Odysseus, célèbre pour le vol et les serments trompeurs. Il participe au nom et à l’héritage rusé du héros."),
    rule("iros", "Iros", "Iros, surnom du mendiant Arnaios, formé sur Iris, messagère des dieux. Sa fonction dérisoire consiste à porter des messages pour obtenir de la nourriture."),
    rule("theoclymene", "Théoklyménos", "Théoclymène, devin fugitif accueilli par Tèlémakhos. Ses présages annoncent le retour du roi et la catastrophe des prétendants."),
    rule("halitherses", "Halithersès", "Halithersès, vieil interprète des oiseaux. Dès l’assemblée d’Ithakè, il lit correctement les signes du retour d’Odysseus."),
    rule("olympos", "Olympos", "L’Olympe, demeure des dieux. Dans la géographie poétique, c’est un espace stable et sans intempéries, opposé aux errances humaines."),
    rule("troie", ("Troiè", "Ilios"), "Troie, appelée aussi Ilios, ville dont la chute clôt la guerre racontée en partie dans l’<em>Iliade</em>. L’<em>Odyssée</em> commence après sa destruction."),
    rule("pylos", "Pylos", "Pylos, royaume de Nestôr dans le Péloponnèse occidental. Tèlémakhos y rencontre une société ordonnée par les rites, la mémoire et la transmission entre générations."),
    rule("lacedemone", ("Spartè", "Lakédaimôn", "Sparta"), "Sparte — dont le territoire est aussi appelé Lacédémone — est le royaume de Ménélaos. Son palais restauré contraste avec la maison d’Odysseus occupée par les prétendants."),
    rule("crete", "Krètè", "La Crète, grande île au carrefour des routes méditerranéennes. Odysseus l’utilise souvent comme origine vraisemblable dans ses récits mensongers."),
    rule("cicones", "Kikônes", "Les Cicones, peuple thrace allié de Troie. Le pillage de leur ville est la première faute des compagnons après le départ de Troie."),
    rule("lotophages", "Lotophages", "Les Lotophages, « mangeurs de lotus ». Leur nourriture n’est pas mortelle : elle efface le désir du retour, menace centrale du poème."),
    rule("cyclopes", ("Kyklôpes", "Kyklôps"), "Les Cyclopes, géants à l’œil unique dans la tradition. Chez Homère, ils vivent sans assemblées, agriculture ni lois communes : leur monstruosité est aussi sociale."),
    rule("lestrygons", ("Laistrygones", "Laistrygons"), "Les Lestrygons, peuple gigantesque et anthropophage. Leur attaque détruit toute la flotte sauf le navire qu’Odysseus avait prudemment laissé hors du port."),
    rule("aiolie", "Aioliè", "Éolie, île flottante d’Aiolos, entourée d’un mur d’airain. Sa géographie merveilleuse signale l’entrée dans un espace éloigné du monde ordinaire."),
    rule("aiaie", "Aiaiè", "Aiaié, île de Kirkè située aux confins orientaux du monde. Elle est associée aux levers de Hèlios et d’Éôs."),
    rule("thrinacie", "Thrinakiè", "Thrinacie, île des troupeaux sacrés de Hèlios. L’interdit qui y est transgressé accomplit l’annonce placée dès les premiers vers du poème."),
    rule("erebe", "Érébos", "L’Érèbe, région obscure du monde souterrain. Le mot désigne ici les ténèbres d’où viennent les âmes des morts."),
    rule("aithiopiens", "Aithiopiens", "Les Éthiopiens homériques habitent les extrémités orientale et occidentale du monde. Leur proximité avec les dieux marque les marges de la géographie épique."),
    rule("agora", "agora", "L’<em>agora</em> est l’assemblée et le lieu où elle se réunit. La capacité à y prendre la parole est un signe essentiel de maturité politique."),
    rule("hecatombe", "hécatombe", "Une hécatombe est un grand sacrifice public de bétail ; le terme signifie littéralement « cent bœufs », sans imposer toujours ce nombre exact."),
    rule("kratere", ("kratère", "kratères"), "Le cratère est le grand vase dans lequel on mélange le vin et l’eau avant de le répartir entre les convives."),
    rule("libation", ("libation", "libations"), "La libation consiste à verser une part de vin ou d’un autre liquide en offrande aux dieux, avant de boire ou d’entreprendre une action."),
    rule("aoide", ("Aoide", "aoide", "Aoides"), "L’aède est un poète-chanteur qui compose et transmet les récits héroïques avec accompagnement musical. Dèmodokos et Phèmios reflètent, dans le poème, l’art qui produit l’<em>Odyssée</em> elle-même."),
    rule("kithare", "kithare", "La cithare est un instrument à cordes pincées, associé au chant de l’aède et aux fêtes aristocratiques."),
    rule("ambroisie", ("ambroisie", "ambroisiennes"), "L’ambroisie est la nourriture ou substance parfumée des immortels. Elle peut nourrir, préserver un corps ou masquer une odeur humaine."),
    rule("nektar", "nektar", "Le nectar est la boisson des dieux. L’orthographe « nektar » reflète le choix de translittération grecque de Leconte de L’Isle."),
    rule("knemides", "knèmides", "Les cnémides sont des jambières de bronze protégeant le tibia ; « Akhaiens aux belles knèmides » est une épithète guerrière formulaire."),
    rule("paroles_ailees", "paroles ailées", "Cette formule suggère que la parole vole du locuteur vers l’auditeur. Sa répétition est caractéristique d’une poésie issue de la composition orale."),
    rule("yeux_clairs", "aux yeux clairs", "Épithète traditionnelle d’Athènè ; le grec <em>glaukôpis</em> peut évoquer des yeux brillants, pers ou de chouette."),
    rule("hospitalite", "hospitalité", "L’hospitalité, ou <em>xenia</em>, crée une relation durable entre hôte et étranger : accueil, repas, questions puis présents. Zeus en est le garant."),
    rule("daimon", "daimôn", "Un <em>daimôn</em> est une puissance divine envisagée dans son action, pas nécessairement un « démon » au sens chrétien."),
    rule("sceptre", "sceptre", "Le sceptre autorise la parole publique et manifeste une fonction de commandement ou de jugement."),
    rule("heraut", ("héraut", "hérauts"), "Le héraut est un agent public protégé par son caractère sacré. Il convoque, transmet les ordres, sert les assemblées et accompagne les cérémonies."),
    rule("nymphes", ("Nymphe", "Nymphes"), "Les nymphes sont des divinités féminines liées à des lieux naturels — sources, arbres, grottes ou rivages. Immortelles ou très longévives, elles n’ont pas le même rang que les grands dieux olympiens."),
    rule("phorkys", ("Phorkyn", "Phorkys"), "Phorkys est une ancienne divinité marine, père de Thoôsa et donc grand-père de Polyphèmos. Le port d’Ithakè qui porte son nom est placé sous ce même imaginaire marin."),
    rule("thoosa", "Thoôsa", "Thoôsa, nymphe marine fille de Phorkys, est la mère du Kyklôps Polyphèmos avec Poseidaôn."),
    rule("iles_ioniennes", ("à Doulikios, à Samè, à Zakyntos", "Doulikhios, de Samè et de Zakynthos", "Doulikhios"), "Doulikhios, Samè et Zakynthos sont des îles voisines d’Ithakè. Leurs chefs fournissent une grande partie des prétendants et appartiennent à la sphère politique d’Odysseus."),
    rule("mycenes", "Mykènè", "Mycènes, cité d’Agamemnôn dans le nord-est du Péloponnèse, est l’un des grands centres du monde achéen associé à la guerre de Troie."),
    rule("harpyes", "Harpyes", "Les Harpyes sont des puissances ailées de la tempête et du rapt. Dire qu’elles ont enlevé quelqu’un revient ici à imaginer une disparition sans trace ni sépulture."),
    rule("themis", "Thémis", "Thémis personnifie l’ordre juste, les usages et le droit de l’assemblée. Sa présence souligne que la réunion du peuple possède une dimension religieuse autant que politique."),
    rule("moire", ("Moire", "Moires", "moire"), "La Moire est la part de destin attribuée à chacun ; au pluriel, les Moires sont les puissances qui la filent. Elle fixe notamment la limite de la vie, sans supprimer toute responsabilité humaine."),
    rule("ker", ("Kèr", "kèr", "kères"), "La <em>kèr</em> est la mort fatale envisagée comme une puissance qui saisit sa victime ; les Kères peuvent être personnifiées. Le mot associe donc l’idée de mort à celle d’un destin funeste."),
    rule("erinyes", ("Érinnyes", "Érinnys", "Érinnyes"), "Les Érinyes sont des divinités de la vengeance qui poursuivent surtout les fautes contre la famille, le sang et les serments. Elles défendent un ordre que la justice humaine ne suffit pas toujours à garantir."),
    rule("augures", ("augures", "augure"), "Les augures sont des signes, souvent tirés du vol des oiseaux, par lesquels une volonté divine peut être interprétée. Leur sens dépend toutefois du savoir et de l’autorité du devin."),
    rule("agorete", "agorète", "Un agorète est un homme habile à parler dans l’assemblée. Le terme peut être honorifique ou, comme ici dans la bouche d’Antinoos, ironique et agressif."),
    rule("neleus", "Nèleus", "Nélée, père de Nestôr et ancien roi de Pylos, rattache le vieux conseiller à l’une des grandes lignées héroïques du Péloponnèse."),
    rule("priam", "Priamos", "Priam, vieux roi de Troie et père d’Hektôr et de Pâris, incarne la dynastie vaincue lors de la prise de la ville."),
    rule("patrocle", ("Patroklos", "Mènoitiade"), "Patrocle, fils de Ménoitios et compagnon le plus proche d’Akhilleus, meurt dans l’<em>Iliade</em>. « Mènoitiade » est son patronymique."),
    rule("antiloque", "Antilokhos", "Antiloque, fils de Nestôr, est un jeune héros achéen tué à Troie. Dans le monde des morts, il demeure associé à Akhilleus et Patroklos."),
    rule("diomede", ("Diomèdès", "Tydéide"), "Diomède, fils de Tydeus — d’où le patronymique « Tydéide » — est l’un des principaux guerriers achéens de l’<em>Iliade</em> et réussit son retour."),
    rule("idomenee", "Idoméneus", "Idoménée, roi crétois et chef d’un contingent achéen à Troie, est cité parmi les rares héros revenus sans perdre leurs hommes."),
    rule("philoctete", "Philoktètès", "Philoctète est l’archer détenteur de l’arc d’Hèraklès. Abandonné puis rappelé à Troie, il est nécessaire à la prise de la ville."),
    rule("egypte", ("Aigyptos", "Aigyptiè"), "Aigyptos désigne l’Égypte et parfois son grand fleuve. Dans l’<em>Odyssée</em>, ce pays lointain est associé aux richesses, aux remèdes et au savoir ancien."),
    rule("pharos", "Pharos", "Pharos est l’île située au large de l’Égypte où Ménélaos reste immobilisé. Bien avant le célèbre phare hellénistique, son nom appartient déjà à la géographie homérique."),
    rule("selene", ("Sélénè", "Séléné"), "Séléné est la Lune personnifiée, sœur de Hèlios dans plusieurs généalogies. Sa lumière sert ici de mesure à l’éclat surnaturel des palais."),
    rule("polydamna", "Polydamna", "Polydamna, femme égyptienne de Thôn, donne à Hélénè le népenthès. Elle représente le savoir pharmaceutique que le poème attribue à l’Égypte."),
    rule("rhadamanthe", "Rhadamanthos", "Rhadamanthe, fils de Zeus et juge réputé pour sa justice, réside selon la tradition dans l’au-delà bienheureux. Les Phaiakiens peuvent le rejoindre aux confins du monde."),
    rule("elysee", ("plaine Élysienne", "Élysienne"), "La plaine Élysienne est un séjour privilégié réservé à quelques héros : climat doux, vie sans peine et absence de mort ordinaire. Ménélaos y est destiné en tant que gendre de Zeus."),
    rule("tithon", "Tithôn", "Tithonos est l’amant mortel d’Éôs. La déesse obtient pour lui l’immortalité mais non la jeunesse éternelle : son histoire rappelle que l’absence de mort n’abolit pas nécessairement le déclin."),
    rule("demeter", "Dèmètèr", "Déméter, déesse des moissons et de la fécondité de la terre, est évoquée ici dans son union avec le mortel Iasiôn."),
    rule("orion", "Oriôn", "Orion est un chasseur géant aimé d’Éôs puis tué par Artémis. Aux Enfers, son ombre poursuit encore les bêtes sauvages, comme si la chasse continuait après la mort."),
    rule("gaia", "Gaia", "Gaia est la Terre personnifiée et une puissance divine primordiale. L’invoquer avec le Ciel et le Styx donne au serment une portée cosmique."),
    rule("styx", "Styx", "Le Styx est le fleuve infernal par lequel les dieux prononcent leur serment le plus contraignant. Le parjure divin y entraîne une lourde sanction."),
    rule("pleiades", "Plèiades", "Les Pléiades sont un amas d’étoiles utilisé comme repère saisonnier et nautique. Odysseus les observe pour maintenir sa route en pleine mer."),
    rule("solymes", "Solymes", "Les Solymes sont un peuple légendaire d’Asie Mineure. Poseidaôn, revenant d’Éthiopie, aperçoit Odysseus depuis leurs montagnes."),
    rule("amphitrite", "Amphitritè", "Amphitrite est une déesse marine, épouse de Poseidaôn. Son nom peut aussi personnifier la mer elle-même et ses créatures."),
    rule("nausithoos", "Nausithoos", "Nausithoos, père d’Alkinoos, conduisit les Phaiakiens jusqu’à Skhériè et fonda leur cité loin des Kyklôpes."),
    rule("charites", "Kharites", "Les Charites, ou Grâces, sont des déesses de la beauté, de l’agrément et de la fête. Elles président notamment à la parure et à la danse."),
    rule("leto", "Lètô", "Léto, mère d’Apollôn et d’Artémis, apparaît dans les comparaisons qui soulignent la beauté et la stature de ses enfants."),
    rule("delos", "Dèlos", "Délos, île sacrée où naquirent Apollôn et Artémis, est un grand sanctuaire du monde grec. Odysseus dit y avoir vu le jeune palmier auquel il compare Nausikaa."),
    rule("laodamas", "Laodamas", "Laodamas, fils d’Alkinoos, est l’un des meilleurs athlètes phaiakiens et invite avec tact l’étranger à participer aux jeux."),
    rule("euryalos", "Euryalos", "Euryalos est le Phaiakien qui provoque Odysseus en mettant en doute sa valeur athlétique. Il reconnaît ensuite sa faute et lui offre une épée."),
    rule("heracles", ("Héraklès", "Hèraklès"), "Héraklès, fils de Zeus, accomplit les célèbres travaux imposés par Eurysthée. L’<em>Odyssée</em> le montre aussi comme archer et comme ombre héroïque aux Enfers."),
    rule("eurytos", "Eurytos", "Eurytos, roi d’Oikhalia et archer exceptionnel, osa rivaliser avec Apollôn. Son arc passe ensuite à son fils Iphitos puis à Odysseus."),
    rule("tityos", "Tityos", "Tityos est un géant puni aux Enfers pour avoir agressé Lètô : deux vautours lui dévorent sans fin le foie."),
    rule("maron", "Maron", "Maron, prêtre d’Apollôn à Ismaros, offre à Odysseus le vin extraordinairement fort qui servira à enivrer Polyphèmos."),
    rule("telemos", "Tèlémos", "Télémos est le devin des Kyklôpes qui avait prédit à Polyphèmos qu’il serait aveuglé par Odysseus."),
    rule("aietes", "Aiètès", "Aiétès, roi de Kolkhis et frère de Kirkè, est le gardien de la Toison d’or dans le cycle des Argonautes."),
    rule("antiphates", "Antiphatès", "Antiphatès est le roi des Laistrygons. Il donne le signal du massacre des équipages grecs après avoir dévoré l’un des éclaireurs."),
    rule("polytes", "Polytès", "Politès est l’un des compagnons les plus proches d’Odysseus. Chez Kirkè, il encourage les hommes à répondre au chant qui les attire vers la demeure."),
    rule("fleuves_enfers", ("Kokytos", "Pyriphlégéthôn"), "Le Kokytos, fleuve des lamentations, et le Pyriphlégéthôn, fleuve de feu, appartiennent à la géographie des Enfers et rejoignent l’Akhérôn près du lieu du sacrifice."),
    rule("kimmeriens", "Kimmériens", "Les Cimmériens habitent, dans la géographie poétique, un pays perpétuellement privé de soleil aux limites du monde des vivants."),
    rule("tyro", "Tyrô", "Tyro, fille de Salmoneus, est la première grande héroïne du catalogue des femmes aux Enfers. De son union avec Poseidaôn naissent Pélias et Nélée."),
    rule("oedipe", "Oidipous", "Œdipe, roi de Thèbes, découvre qu’il a tué son père et épousé sa mère Épikastè. Le passage résume une tradition antérieure aux tragédies conservées."),
    rule("dioscures", ("Kastor", "Polydeukès"), "Castor et Polydeucès, fils de Lèdè et de Tyndaros, sont les Dioscures. Ils alternent entre vie et mort et reçoivent tous deux des honneurs divins."),
    rule("aloadai", ("Otos", "Éphialtès"), "Otos et Éphialtès sont les Aloades, deux géants qui tentèrent d’empiler les montagnes pour attaquer l’Olympe. Apollôn les tua avant l’âge adulte."),
    rule("minos", "Minôs", "Minos, roi légendaire de Krètè et fils de Zeus, rend encore la justice parmi les morts, sceptre en main."),
    rule("ariadne", "Ariadnè", "Ariane, fille de Minôs, aide Thèseus à sortir du labyrinthe. Le récit homérique évoque ensuite sa mort à Diè sur l’intervention de Dionysos."),
    rule("dionysos", "Dionysos", "Dionysos, dieu du vin, de l’extase et du théâtre, intervient ici dans le destin d’Ariadnè ; il offrira aussi l’urne funéraire d’Akhilleus."),
    rule("thesee", "Thèseus", "Thésée, héros athénien vainqueur du Minotaure, est lié à Ariadnè puis à Peirithoos. Odysseus espère apercevoir ces deux héros parmi les morts."),
    rule("sisyphe", "Sisyphos", "Sisyphe est condamné dans les Enfers à pousser éternellement un rocher qui retombe avant le sommet : image d’un effort sans terme ni accomplissement."),
    rule("tantale", "Tantalos", "Tantale subit une faim et une soif éternelles au milieu d’eau et de fruits qui se dérobent dès qu’il tente de les atteindre."),
    rule("cerbere", "Kerbéros", "Cerbère est le chien monstrueux qui garde l’entrée des Enfers. Le ramener vivant fut l’un des travaux imposés à Héraklès."),
    rule("gorgone", "Gorgônien", "La Gorgone est un monstre dont le regard pétrifie. Odysseus craint ici que Perséphonéia ne lui envoie sa tête depuis les profondeurs d’Hadès."),
    rule("cassandre", "Kassandrè", "Cassandre, fille de Priam et prophétesse troyenne, est emmenée comme captive par Agamemnôn puis tuée avec lui dans le palais."),
    rule("neoptoleme", "Néoptolémos", "Néoptolème, fils d’Akhilleus, rejoint les Achéens à la fin de la guerre et combat dans le cheval de bois. Odysseus loue ici sa valeur et sa maîtrise de soi."),
    rule("memnon", "Memnôn", "Memnon, roi venu d’Éthiopie au secours de Troie, tue Antilokhos avant d’être vaincu par Akhilleus."),
    rule("epeios", "Épéios", "Épéios est l’artisan qui construit le cheval de bois avec l’aide d’Athènè. Il en ouvre aussi la trappe lorsque les guerriers achéens sortent dans Troie."),
    rule("hebe", "Hèbè", "Hébé, déesse de la jeunesse, devient l’épouse d’Héraklès après son admission parmi les dieux."),
    rule("peirithoos", "Peirithoos", "Peirithoos, roi des Lapithes et ami de Thèseus, descend avec lui aux Enfers dans une expédition qui tourne au désastre."),
    rule("argonautes", ("Argô", "Jèsôn"), "L’Argô est le navire de Jason et des Argonautes partis chercher la Toison d’or. Il est le seul navire que la tradition dit avoir franchi les Roches Errantes."),
    rule("filles_helios", ("Lampétiè", "Phaéthousa"), "Lampétie et Phaéthousa, filles de Hèlios et de la nymphe Néaira, gardent sur Thrinakiè les troupeaux sacrés de leur père."),
    rule("dodone", "Dôdônè", "Dodone, sanctuaire oraculaire de Zeus en Épire, rend ses réponses à travers le bruissement du chêne sacré."),
    rule("melampous", "Mélampous", "Mélampous est un devin célèbre et l’ancêtre de Théoklyménos. Son histoire explique le prestige prophétique de cette lignée."),
    rule("pheniciens", "Phoinikes", "Les Phéniciens sont présentés comme des navigateurs et marchands au long cours, mais aussi comme des ravisseurs rusés : image grecque ambivalente d’un peuple maritime concurrent."),
    rule("peiraios", "Peiraios", "Peiraios est un compagnon fidèle de Tèlémakhos. Il accueille Théoklyménos et conserve les présents rapportés du voyage."),
    rule("parnassos", "Parnèsos", "Le Parnasse est la montagne où le jeune Odysseus, accueilli par son grand-père Autolykos, reçoit de la chasse au sanglier la cicatrice qui permettra sa reconnaissance."),
    rule("ilithyies", "Ilithyies", "Les Ilithyies sont les déesses qui président aux douleurs et à l’accomplissement de l’accouchement. Leur grotte près de Knôssos sert ici de repère géographique."),
    rule("aedon", "Aèdôn", "Aédon, changée en rossignol, pleure éternellement son fils Itylos qu’elle a tué par erreur. Pènélopéia compare à ce chant son hésitation et son deuil."),
    rule("eurynome", "Eurynomè", "Eurynomé est une servante fidèle de Pènélopéia. Elle prépare le siège d’Odysseus déguisé et participe aux soins de la maison."),
    rule("melantho", "Mélanthô", "Mélantho, servante élevée par Pènélopéia, trahit pourtant la maison et insulte Odysseus déguisé ; elle est liée au prétendant Eurymakhos."),
    rule("ctesippe", "Ktèsippos", "Ctésippe est le prétendant qui lance un pied de bœuf contre Odysseus en appelant ce geste un présent d’hospitalité. Il pousse ainsi la profanation jusqu’à la parodie rituelle."),
    rule("agelaos", "Agélaos", "Agélaos, fils de Damastôr, prend la direction des prétendants pendant le combat final après la mort de leurs premiers meneurs."),
    rule("iphitos", "Iphitos", "Iphitos, fils d’Eurytos, donna à Odysseus le grand arc de son père. Leur échange de présents fonde une amitié d’hospitalité interrompue par la mort d’Iphitos."),
    rule("leiodès", ("Leiôdès", "Léiôdès"), "Léiodès est le devin des prétendants. Il condamne certains de leurs excès, mais reste associé au groupe qui occupe la maison et périt avec lui."),
    rule("eurytion", "Eurythiôn", "Eurytion est le Centaure qui, ivre aux noces de Peirithoos, attaque les femmes des Lapithes. Son exemple sert d’avertissement contre la démesure provoquée par le vin."),
    rule("ekhetos", "Ékhétos", "Échétos est un roi proverbialement cruel, invoqué comme menace contre ceux que l’on veut effrayer ou châtier."),
    rule("amphimedon", "Amphimédôn", "Amphimédon est un prétendant d’Ithakè. Après sa mort, son âme raconte à Agamemnôn la ruse de la toile et le massacre dans le palais."),
    rule("dolios", "Dolios", "Dolios est le vieux serviteur attaché au domaine de Laertès et père de plusieurs travailleurs restés fidèles à la maison d’Odysseus."),
    rule("eupeithes", "Eupeithès", "Eupithès, père d’Antinoos, mène les familles des prétendants contre Odysseus. Sa tentative de vendetta provoque le dernier affrontement du poème."),
    rule("thetis", "Thétis", "Thétis, déesse marine et mère d’Akhilleus, conduit les Néréides au deuil de son fils et fournit les prix de ses jeux funèbres."),
    rule("hellespont", "Hellespontos", "L’Hellespont, détroit aujourd’hui appelé Dardanelles, sépare l’Europe de l’Asie près de Troie. Le tombeau d’Akhilleus y reste visible des navigateurs."),
    rule("cephalleniens", ("Képhallèniens", "Képhalléniens"), "Les Céphalléniens sont les populations insulaires placées sous l’autorité d’Odysseus, notamment à Ithakè et dans les îles voisines."),
    rule("suppliant", ("suppliant", "suppliants"), "Le suppliant se place sous la protection religieuse de celui qu’il implore, souvent en touchant ses genoux ou son menton. Le repousser violemment peut constituer une faute envers Zeus."),
    rule("throne", ("thrône", "thrônes"), "Le <em>thrône</em> est un siège d’honneur à dossier, réservé aux rois, aux hôtes distingués ou aux dieux ; l’orthographe archaïsante reproduit ici le grec <em>thronos</em>."),
    rule("talent", ("talent", "talents"), "Le talent est une unité de poids servant à mesurer les métaux précieux, non une monnaie frappée. Sa valeur exacte varie selon les époques et les régions."),
    rule("trepied", ("trépied", "trépieds"), "Le trépied est un chaudron ou support à trois pieds, objet prestigieux offert aux sanctuaires, aux hôtes ou comme prix de concours."),
    rule("coudee", ("coudée", "coudées"), "La coudée est une mesure fondée sur la longueur de l’avant-bras, approximativement un demi-mètre selon les systèmes anciens."),
]


EVENTS = [
    Event(1, "Dis-moi, Muse", "L’invocation place le récit sous l’autorité de la Muse. L’action commence <em>in medias res</em> : Troie est déjà tombée et Odysseus demeure loin d’Ithakè."),
    Event(1, "aggravent leur destinée", "Dès l’ouverture, Zeus affirme que les humains ajoutent par leurs choix aux maux venus du destin. La responsabilité humaine restera un axe majeur du poème."),
    Event(1, "semblable à un étranger", "Le déguisement permet à Athènè de conseiller sans abolir l’initiative humaine : Tèlémakhos doit transformer l’encouragement divin en décision personnelle."),
    Event(1, "le retour fatal des Akhaiens", "Le chant de Phèmios introduit un récit dans le récit. Les auditeurs de l’<em>Odyssée</em> voient comment la mémoire de Troie agit différemment sur chaque personnage."),
    Event(2, "une grande toile, large et fine", "La ruse du linceul suspend le remariage : Pènélopéia tisse le jour et défait la nuit. Le tissage devient l’équivalent domestique des ruses d’Odysseus."),
    Event(2, "deux aigles qui s'enlevèrent", "Dans l’épopée, le vol des oiseaux peut manifester une volonté divine. Halithersès interprète ces aigles comme l’annonce du retour et de la vengeance d’Odysseus."),
    Event(2, "le sceptre en main", "Le geste fait entrer Tèlémakhos dans la parole politique adulte. Son autorité reste contestée, mais elle devient publiquement visible."),
    Event(2, "semblable à Mentôr par l'aspect et par la voix", "Athènè anime le départ en empruntant une identité reconnue à Ithakè. Le divin agit ici par confiance sociale autant que par miracle."),
    Event(3, "un triste retour aux Akhaiens", "Les <em>nostoi</em>, récits des retours après Troie, formaient un vaste cycle traditionnel. L’histoire d’Odysseus s’inscrit parmi ces destins divergents."),
    Event(3, "une génisse d'un an", "Le sacrifice suit une séquence précise : consécration, mise à mort, combustion de la part divine, partage et repas. Le rite relie communauté, mémoire et présence des dieux."),
    Event(3, "le cavalier Gérennien Nestôr", "Cette épithète associe Nestôr à Gérénia, lieu de Messénie. Les épithètes homériques identifient le personnage et s’insèrent dans le rythme du vers."),
    Event(
        3,
        "Irions-nous par le nord de l'âpre Khios",
        (
            "À Lesbos, les chefs hésitent entre une route extérieure près de Psyriè "
            "(l’actuelle Psara) et une route intérieure entre Khios et le cap Mimas, "
            "sur la côte ionienne. Le présage les conduit finalement à travers la mer "
            "ouverte jusqu’à Géraistos, port situé à l’extrémité sud de l’Euboia."
            "<figure class='annotation-map'>"
            "<a href='assets/carte-retour-egee.svg' target='_blank' rel='noopener noreferrer'>"
            "<img src='assets/carte-retour-egee.svg' alt='Carte schématique du choix de route entre Lesbos, Khios, Psyriè, Mimas et Géraistos'>"
            "</a>"
            "<figcaption>Les traits pointillés montrent les deux options débattues ; le "
            "trait bleu montre la traversée retenue après le signe de Zeus. Le tracé est "
            "schématique, mais les positions relatives des lieux sont géographiques.</figcaption>"
            "</figure>"
        ),
    ),
    Event(4, "un baume, le népenthès", "Le fameux <em>nèpenthès</em>, venu d’Égypte, suspend la douleur et les larmes. Le passage interroge le rapport entre récit, mémoire et oubli du traumatisme."),
    Event(4, "Vieillard de la mer", "Pour obtenir la vérité de Prôteus, il faut maintenir la prise malgré ses formes successives. La maîtrise physique devient une épreuve de constance interprétative."),
    Event(4, "se changea d'abord en un lion", "La série des métamorphoses de Prôteus a donné l’adjectif « protéiforme ». Ménélaos gagne le savoir en refusant de se laisser tromper par l’apparence."),
    Event(4, "retenu au milieu de la mer large", "Ménélaos apporte la première information fiable sur Odysseus : il vit, mais demeure empêché de rentrer. La quête de Tèlémakhos atteint donc son but essentiel."),
    Event(5, "assis sur les rochers et sur les rivages", "L’immortalité offerte par Kalypsô ne console pas Odysseus. Son désir porte vers une vie mortelle, mais située dans une histoire, une famille et une terre."),
    Event(5, "fais un large radeau", "Après des années de captivité, le retour recommence par un travail technique. Le héros survit autant comme artisan que comme guerrier."),
    Event(5, "Inô aux beaux talons", "L’intervention d’Inô-Leukothéè offre une aide conditionnelle : Odysseus doit abandonner son radeau et faire confiance à un objet divin sans renoncer à nager."),
    Event(5, "deux arbustes entrelacés", "L’olivier sauvage et l’olivier cultivé offrent un refuge naturel. Cette association prépare symboliquement le retour du héros sauvage et nu vers la vie civilisée."),
    Event(6, "je lave nos beaux vêtements", "Le rêve envoyé par Athènè mêle une tâche domestique réelle à l’horizon du mariage. Il conduit Nausikaa exactement au lieu du naufrage."),
    Event(6, "la jeune reine jeta une balle", "Athènè provoque indirectement le cri qui réveille Odysseus. Le hasard apparent est ainsi présenté comme une action divine discrète."),
    Event(6, "un rameau épais afin de voiler sa nudité", "Nu et couvert de sel, Odysseus doit se présenter sans effrayer les jeunes filles. La scène réduit le héros à la parole, à la pudeur et au jugement."),
    Event(6, "s'il saisissait ses genoux", "Odysseus remplace le geste physique du suppliant par une adresse à distance. Cette retenue protège Nausikaa et manifeste son intelligence sociale."),
    Event(7, "Va d'abord à la reine", "Dans le palais phéacien, le succès dépend d’Arètè. Le conseil reconnaît une autorité féminine décisive dans l’accueil de l’étranger."),
    Event(7, "l'enveloppa d'un épais brouillard", "Athènè rend Odysseus invisible pendant sa traversée de la ville. La protection cesse au moment où il doit lui-même parler et convaincre."),
    Event(7, "chiens d'or et d'argent", "Les automates fabriqués par Hèphaistos donnent au palais une splendeur surnaturelle. La technique divine y imite et dépasse le vivant."),
    Event(8, "la querelle d'Odysseus", "Dèmodokos chante un épisode de Troie absent de l’<em>Iliade</em>. La tradition épique apparaît comme un ensemble plus vaste que les deux poèmes conservés."),
    Event(8, "pleurait, la tête cachée", "Odysseus pleure en secret à l’écoute de sa propre histoire. Le héros guerrier devient aussi l’auditeur vulnérable de la poésie qui le rend célèbre."),
    Event(8, "une pierre plus grande", "Provoqué par Euryalos, Odysseus réaffirme son identité héroïque par un lancer exceptionnel. L’exploit prépare la révélation verbale de son nom."),
    Event(8, "l'amour d'Arès et d'Aphroditè", "Le chant comique de l’adultère d’Arès et d’Aphroditè offre un contrepoint aux unions humaines. Hèphaistos y triomphe par l’intelligence technique, non par la force."),
    Event(
        9,
        "je suis Odysseus Laertiade",
        (
            "Après avoir longtemps gardé l’anonymat, le héros révèle son nom aux "
            "Phaiakiens. Cette déclaration ouvre le grand récit rétrospectif des errances. "
            "Une carte globale peut aider à suivre les épisodes, mais les identifications "
            "des terres merveilleuses restent conjecturales."
            "<figure class='annotation-map'>"
            "<a href='assets/carte-voyages-butler.png' target='_blank' rel='noopener noreferrer'>"
            "<img src='assets/carte-voyages-butler.png' alt='Carte historique des voyages d’Ulysse proposée par Samuel Butler en 1900'>"
            "</a>"
            "<figcaption>La reconstruction de Samuel Butler (1900) est une hypothèse "
            "historique parmi d’autres, et non la géographie certaine du poème. "
            "<a class='annotation-map-source' href='https://commons.wikimedia.org/wiki/File:Odyssey_(Butler)_Map.png' target='_blank' rel='noopener noreferrer'>"
            "Carte du domaine public — Wikimedia Commons</a>.</figcaption>"
            "</figure>"
        ),
    ),
    Event(9, "terre des kyklopes orgueilleux et sans lois", "Le récit juge les Kyklôpes à partir des institutions grecques : agriculture, assemblée, lois, navigation et hospitalité. Leur altérité est construite comme absence de vie civique."),
    Event(9, "mon nom est Personne", "Le jeu repose sur le grec <em>Outis</em>, « personne ». La ruse fonctionne parce que Polyphèmos transforme involontairement un nom propre en négation."),
    Event(9, "l'enfoncèrent dans l'oeil", "L’aveuglement inverse la force du géant par un savoir technique collectif : bois taillé, feu, levier et coordination."),
    Event(9, "dévastateur de citadelles Odysseus", "En proclamant finalement son vrai nom, Odysseus échange la sécurité contre la gloire. Cette revendication permet à Polyphèmos de lancer sa malédiction à Poseidaôn."),
    Event(10, "une outre, faite de la peau", "Aiolos enferme les vents contraires dans une outre. Les compagnons, croyant qu’elle contient un trésor caché, détruisent par jalousie un retour presque accompli."),
    Event(10, "dans l'intérieur du port", "Le port fermé qui paraît protecteur devient un piège. La prudence d’Odysseus, resté à l’extérieur, sauve un seul navire."),
    Event(10, "la tête, la voix, le corps et les soies du porc", "La métamorphose matérialise la perte de maîtrise provoquée par le festin enchanté. Les compagnons conservent pourtant leur conscience humaine."),
    Event(10, "les dieux la nomment môly", "Cette herbe divine à la racine noire et à la fleur blanche protège des enchantements de Kirkè. Son nom réservé aux dieux souligne l’écart entre savoir divin et savoir humain ; Hermès fournit à Odysseus un moyen d’affronter l’épreuve, non de l’éviter."),
    Event(10, "demeure d'Aidès", "Le chemin du retour exige paradoxalement un détour par le monde des morts. Odysseus doit obtenir un savoir que le monde des vivants ne peut lui donner."),
    Event(11, "une fosse d'une coudée", "La consultation des morts suit un rituel de séparation et d’appel : fosse, libations, farine, sang sacrificiel et promesse d’offrandes futures."),
    Event(11, "le sang noir", "Les âmes ont besoin du sang pour retrouver momentanément mémoire, parole et reconnaissance. Odysseus contrôle ainsi l’ordre des témoignages."),
    Event(11, "un fléau sur ta brillante épaule", "La prophétie de Teirésias conduira Odysseus là où une rame sera prise pour un instrument agricole : image d’un monde qui ignore la mer et où devra s’apaiser Poseidaôn."),
    Event(11, "je m'élançai trois fois", "Odysseus tente d’embrasser l’ombre de sa mère, mais ses bras se referment sur le vide. La répétition donne une forme sensible à l’irréversibilité de la mort."),
    Event(11, "j'aimerais mieux être", "Achille renverse ici l’idéal héroïque : mieux vaut la vie obscure d’un serviteur que la souveraineté parmi les morts. La gloire ne compense pas la disparition du vivant."),
    Event(12, "je fermai les oreilles", "La cire protège les rameurs, tandis qu’Odysseus se fait attacher pour entendre sans pouvoir céder. Il transforme une tentation mortelle en expérience contrôlée."),
    Event(12, "liez-moi fortement", "Le héros anticipe sa propre faiblesse et délègue sa maîtrise à des liens et à l’obéissance de l’équipage : une forme de prudence fondée sur l’engagement préalable."),
    Event(12, "D'un côté était Skyllè", "Le passage entre Skyllè et Kharybdis impose une décision tragique : accepter une perte limitée plutôt que risquer la destruction totale."),
    Event(12, "meilleurs boeufs de Hèlios", "Affamés, les compagnons transforment volontairement le sacrilège en sacrifice. Le langage rituel ne peut rendre légitime ce que l’interdit divin condamne."),
    Event(13, "le déposèrent endormi sur le sable", "Le retour s’accomplit pendant le sommeil du héros. Il atteint enfin Ithakè sans voir le passage décisif, transporté par l’hospitalité phéacienne."),
    Event(13, "la transforma en rocher", "La pétrification du navire accomplit l’ancienne menace de Poseidaôn. Les Phaiakiens paient le prix d’avoir reconduit trop parfaitement l’ennemi du dieu."),
    Event(13, "quelle est cette terre", "Le brouillard d’Athènè rend Ithakè étrangère à son propre roi. Avant de reprendre son identité publique, Odysseus doit réapprendre à voir sa terre."),
    Event(13, "fourbe, menteur, subtil", "Athènè reconnaît dans le mensonge improvisé d’Odysseus une intelligence proche de la sienne. Leur complicité se fonde sur l’art partagé du déguisement."),
    Event(14, "chiens aboyeurs virent Odysseus", "L’arrivée chez Eumaios commence par une menace animale, contrairement à la reconnaissance silencieuse d’Argos plus tard. Le porcher protège l’étranger avant de connaître son identité."),
    Event(14, "les étrangers et les pauvres viennent de Zeus", "Cette maxime résume la <em>xenia</em> : la dignité de l’accueil ne dépend pas du rang apparent du visiteur. Eumaios réussit précisément l’épreuve que les prétendants échouent."),
    Event(14, "né dans la vaste Krètè", "Odysseus construit un récit crétois très détaillé. Le mensonge efficace mêle éléments plausibles, vérités déplacées et motifs de sa véritable expérience."),
    Event(15, "un aigle s'envola à sa droite", "L’aigle emportant une oie domestique est interprété comme l’image d’Odysseus revenant frapper les prétendants dans sa maison."),
    Event(15, "compagnons de Tèlémakhos, ayant abordé", "Le retour de Tèlémakhos rejoint désormais celui de son père. Les deux lignes narratives, séparées depuis le chant I, peuvent se réunir."),
    Event(15, "nous t'accueillerons avec amitié", "En accueillant Théoklyménos, Tèlémakhos applique à son tour l’hospitalité apprise pendant son voyage, malgré le danger politique de recevoir un fugitif."),
    Event(16, "le frappa de sa baguette d'or", "Athènè rend à Odysseus une apparence héroïque pour la reconnaissance par son fils. Le changement extérieur autorise enfin la vérité intérieure."),
    Event(16, "Tu n'es pas mon père Odysseus", "L’incrédulité de Tèlémakhos montre qu’une reconnaissance ne tient pas au seul regard. Elle exige signes, récit et acceptation émotionnelle."),
    Event(16, "ils pleuraient abondamment", "Les pleurs du père et du fils sont comparés aux cris d’oiseaux privés de leurs petits. La reconnaissance héroïque passe par une vulnérabilité partagée."),
    Event(16, "nombre des prétendants", "Avant l’affrontement, Odysseus exige un inventaire précis des forces et des fidélités. La vengeance est préparée comme une opération de renseignement."),
    Event(17, "chien Argos", "Argos reconnaît son maître sans signe ni explication, puis meurt. Cette fidélité immédiate contraste avec l’aveuglement des humains qui occupent la maison."),
    Event(17, "en frappa l'épaule droite", "Antinoos viole l’hospitalité en frappant un mendiant dans la maison d’autrui. Le projectile rend visible une violence déjà contenue dans le festin des prétendants."),
    Event(17, "s'assit sur le seuil", "Installé au point le plus bas de sa propre salle, le roi observe ceux qui le reconnaissent, l’aident ou l’outragent. Le déguisement devient une épreuve morale de la maison."),
    Event(18, "le nommaient tous Iros", "Le duel entre mendiants est organisé comme une parodie de combat héroïque. Sous le spectacle comique, Odysseus mesure encore les réactions de chacun."),
    Event(18, "Pènélopéia, d'apparaître aux prétendants", "Athènè accroît la beauté de Pènélopéia pour attiser le désir des prétendants, mais la reine transforme cette exposition en moyen d’obtenir des présents."),
    Event(18, "accepte les présents", "Pènélopéia rappelle la règle normale de la cour : les prétendants devraient enrichir la maison de la femme au lieu de la dévorer. Sa parole renverse momentanément le pillage."),
    Event(19, "reconnut la cicatrice", "La cicatrice est un signe involontaire, inscrit dans le corps et lié à l’enfance du héros. Eurykléia reconnaît l’homme sous le récit et les haillons."),
    Event(19, "un grand sanglier", "Le récit de la chasse explique la cicatrice et suspend la scène présente. Cette analepse rattache Odysseus à son nom, à son grand-père Autolykos et à une histoire corporelle vérifiable."),
    Event(19, "Vingt oies, sortant de l'eau", "Dans le rêve de Pènélopéia, l’aigle tue les oies puis s’identifie à Odysseus. L’interprétation paraît claire, mais la rêveuse maintient une prudence qui protège sa décision."),
    Event(19, "Les songes sortent par deux portes", "Le jeu entre corne et ivoire distingue rêves véridiques et trompeurs. Pènélopéia refuse de traiter même un signe favorable comme une certitude simple."),
    Event(20, "riaient avec des mâchoires contraintes", "Athènè transforme le rire des prétendants en signe de dérèglement. Le banquet bascule symboliquement vers le spectacle funèbre annoncé par Théoklyménos."),
    Event(20, "un pied de boeuf", "Ktèsippos présente son projectile comme un « présent d’hospitalité ». Cette inversion sacrilège des mots et des gestes appelle directement la vengeance."),
    Event(20, "ces colonnes et ces murailles sont souillées de sang", "La vision de Théoklyménos superpose au festin présent son issue imminente. Les prétendants rient parce qu’ils sont incapables de lire les signes qui les entourent."),
    Event(21, "à travers les douze haches", "L’épreuve de l’arc réunit force, technique et légitimité. L’objet que nul autre ne peut même tendre fonctionne comme un signe matériel du roi absent."),
    Event(21, "aussi aisément qu'un homme, habile à jouer de la kithare", "Odysseus tend l’arc aussi aisément qu’un musicien ajuste une corde. L’image unit la maîtrise guerrière à l’harmonie et annonce un ordre retrouvé par la violence."),
    Event(21, "traversa tous les anneaux", "La flèche franchit les haches sans dévier : la réussite publique met fin au déguisement et donne le signal convenu à Tèlémakhos."),
    Event(22, "se dépouillant de ses haillons", "Le passage du mendiant au roi armé est volontaire et théâtral. L’identité longtemps dissimulée devient soudain une accusation prononcée devant toute la salle."),
    Event(22, "la pointe traversa le cou", "Antinoos meurt au moment où il porte la coupe à ses lèvres. Le banquet qu’il profanait se transforme immédiatement en scène de jugement et de sang."),
    Event(22, "apporter des armes de la chambre haute", "La trahison de Mélanthios change l’équilibre du combat. Eumaios et Philoitios doivent neutraliser l’accès à l’arsenal avant que la force royale puisse l’emporter."),
    Event(22, "l'aoide Terpiade Phèmios", "Phèmios demande grâce au nom de son art et de la contrainte subie. Tèlémakhos confirme qu’il ne servait pas volontairement les prétendants."),
    Event(22, "le câble d'une nef", "L’exécution collective des servantes reflète la dureté de la justice domestique héroïque. Le texte associe leur faute sexuelle à leur alliance active avec les prétendants."),
    Event(23, "je ne puis ni parler, ni interroger", "Pènélopéia refuse une reconnaissance précipitée. Sa réserve n’est pas froideur, mais protection contre l’erreur après vingt années de récits trompeurs."),
    Event(23, "travail de ce lit est un signe certain", "L’épreuve du lit est un mot de passe conjugal que nul étranger ne devrait connaître. Pènélopéia teste Odysseus par une ruse digne de lui."),
    Event(23, "le tronc de l'olivier", "Le lit a été construit autour d’un olivier enraciné dans la chambre. Il figure une union vivante, immobile et indissociable de la maison."),
    Event(23, "les genoux de Pènélopéia défaillirent", "La reconnaissance devient certaine lorsque la colère d’Odysseus révèle le secret du lit. Le signe intellectuel déclenche enfin l’abandon émotionnel."),
    Event(24, "évoqua les âmes des prétendants", "Le dernier chant s’ouvre par une seconde descente aux morts, symétrique de celle d’Odysseus. Les prétendants deviennent désormais un récit soumis au jugement des héros anciens."),
    Event(24, "Heureux fils de Laertès", "Agamemnôn célèbre Pènélopéia et oppose sa fidélité à la trahison de Klytaimnestrè. Le retour d’Odysseus reçoit ainsi sa conclusion dans la mémoire héroïque."),
    Event(24, "j'éprouverai mon père", "Même après la victoire, Odysseus teste Laertès par un récit mensonger. L’habitude de la ruse retarde douloureusement une reconnaissance pourtant désirée."),
    Event(24, "les arbres de ton verger", "Les arbres nommés un à un constituent un signe privé entre père et fils. La mémoire du verger atteste l’identité aussi sûrement que la cicatrice."),
    Event(24, "Ossa se répandit par la ville", "Ossa est la Rumeur personnifiée : la nouvelle du massacre semble courir d’elle-même dans Ithakè et transforme aussitôt une vengeance domestique en crise politique."),
    Event(24, "l'oubli du meurtre", "Athènè et Zeus imposent finalement l’arrêt de la vendetta. La restauration politique exige autre chose que la victoire : une mémoire pacifiée et un accord collectif."),
]


def occurrences(text: str, terms: tuple[str, ...]):
    for term in terms:
        pattern = re.compile(rf"(?<![\wÀ-ÿ]){re.escape(term)}(?![\wÀ-ÿ])", re.IGNORECASE)
        for match in pattern.finditer(text):
            yield match.start(), match.end(), match.group(0)


def overlaps(start: int, end: int, spans: list[dict]) -> bool:
    return any(start < item["end"] and end > item["start"] for item in spans)


def place_event(pages: list[dict], spans: list[list[dict]], event: Event, missed: list[str]) -> None:
    pattern = re.compile(re.escape(event.anchor), re.IGNORECASE)
    for page_index, page in enumerate(pages):
        if page["chant"] != event.chant:
            continue
        match = pattern.search(page["text"])
        if match and not overlaps(match.start(), match.end(), spans[page_index]):
            spans[page_index].append({
                "start": match.start(),
                "end": match.end(),
                "label": match.group(0),
                "body": event.body,
                "key": f"event-{event.chant}-{event.anchor}",
            })
            return
    missed.append(f"chant {event.chant}: {event.anchor}")


def place_rule(
    pages: list[dict],
    spans: list[list[dict]],
    entry: Rule,
    chant: int | None,
) -> bool:
    candidates = []
    for page_index, page in enumerate(pages):
        if chant is not None and page["chant"] != chant:
            continue
        for start, end, matched in occurrences(page["text"], entry.terms):
            if not overlaps(start, end, spans[page_index]):
                candidates.append((page_index, start, end, matched))
    if not candidates:
        return False

    # Une entrée est attachée à sa première occurrence disponible. Une page
    # peut donc être dense si le texte y introduit beaucoup de noms ou notions.
    page_index, start, end, matched = min(
        candidates,
        key=lambda item: (item[0], item[1], -(item[2] - item[1])),
    )
    spans[page_index].append({
        "start": start,
        "end": end,
        "label": matched,
        "body": entry.body,
        "key": entry.key if chant is None else f"{entry.key}-chant-{chant}",
    })
    return True


def annotate(data: list[dict]) -> tuple[list[dict], dict]:
    pages = []
    for source in data:
        page = dict(source)
        page["text"] = MARKER_RE.sub("", page["text"])
        page["notes"] = []
        pages.append(page)

    pristine = [page["text"] for page in pages]
    spans: list[list[dict]] = [[] for _ in pages]
    missed_events: list[str] = []

    for event in EVENTS:
        place_event(pages, spans, event, missed_events)

    missed_glossary = []
    for entry in (item for item in GLOSSARY if item.scope == "book"):
        if not place_rule(pages, spans, entry, None):
            missed_glossary.append(entry.key)

    for chant in range(1, 25):
        for entry in (item for item in GLOSSARY if item.scope == "chant"):
            place_rule(pages, spans, entry, chant)

    for page_index, page in enumerate(pages):
        annotations = sorted(spans[page_index], key=lambda item: (item["start"], item["end"]))
        for number, annotation in enumerate(annotations, start=1):
            annotation["number"] = number

        text = page["text"]
        for annotation in reversed(annotations):
            text = text[:annotation["end"]] + f"[^ {annotation['number']}]".replace(" ", "") + text[annotation["end"]:]
        page["text"] = text
        page["notes"] = [
            {
                "n": annotation["number"],
                "note_html": f"<strong>{html.escape(annotation['label'])} :</strong> {annotation['body']}",
                "key": annotation["key"],
            }
            for annotation in annotations
        ]

    assert [MARKER_RE.sub("", page["text"]) for page in pages] == pristine
    assert all(len(MARKER_RE.findall(page["text"])) == len(page["notes"]) for page in pages)

    by_chant = {
        chant: sum(len(page["notes"]) for page in pages if page["chant"] == chant)
        for chant in range(1, 25)
    }
    report = {
        "total": sum(by_chant.values()),
        "pages_with_notes": sum(bool(page["notes"]) for page in pages),
        "max_on_page": max(len(page["notes"]) for page in pages),
        "by_chant": by_chant,
        "missed_events": missed_events,
        "missed_glossary": missed_glossary,
    }
    return pages, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    annotated, report = annotate(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(annotated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
