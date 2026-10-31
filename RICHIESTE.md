# Richieste del proprietario

Elenco di tutto quello che è stato chiesto, con lo stato. Si aggiorna a ogni richiesta e a ogni
consegna, così niente si perde fra una sessione e l'altra.

Legenda: ⏳ in corso · 📋 da fare · ✅ fatto (con la versione pubblicata)

## In corso e da fare

| # | Richiesta | Stato |
|---|---|---|
| 3 | La **miniatura quadrata** (icona del gioco) non piace: proporne una diversa. | ⏳ (3 proposte) |
| 9 | **Miniatura**: piace la B (uovo-mostro) ma deve dare l'idea che sia **su un picco montuoso**, senza rimpicciolirla troppo. | ⏳ pronte due versioni (con e senza bandierina) in `art/promo/final/`: si carica a mano su Creator Hub (le API non lo permettono) |
| 15 | **Copertine** nuove in Blender (1920×1080) in `art/promo/final/cover_1..4.png`: "STEAL THE EGGS!" (Bacon Hair vero in fuga con l'uovo, Titan Rex), "HATCH GIANT PETS!" (i cinque giganti Ultra e la Balena Cosmica), "EXTREME TRAIL!" (Bacon Hair sulla lava con i diavoli Estremi), "HATCH MONSTERS!" (uovo Primordiale da cui esce il King Cobra). | ⏳ pronte: si caricano a mano su Creator Hub → Thumbnails |
| 7 | Lavorare **in parallelo con gli agenti** e **segnare tutto quello che chiede**, senza perdere nulla. | ⏳ (questo file) |

## Fatte

| Richiesta | Versione |
|---|---|
| Percorso Estremo **più dettagliato**: Abissi (faccia di rana pescatrice all'ingresso, rana pescatrice gigante, relitto con forziere, pinnacoli con cascate, meduse luminose, coralli e alghe sulle sponde), Deserto (porta con sole alato, Sfinge d'oro, piramidi, oasi, facciata del tempio con Anubi e scarabeo), Laboratorio (statua della lince geniale, schermo gigante, bobine di Tesla, cervello in barattolo, vasche luminose, lavagne), Inferno (porta dell'inferno, cascate di lava, ponte di ferro sugli uncini, trono del re demone). 1.704 parti, nessuna si può toccare; sponde uguali nel gioco e nei controlli offline | v47 |
| **Controllo automatico delle compenetrazioni** (`tests/extreme_overlap.py`): 85 problemi visibili trovati e corretti in tutto il Percorso Estremo (deserto compreso: piattaforme che entravano nei santuari e nelle piastrelle, crepe nei pavimenti dei santuari, cartelli nei muri, tronchi che attraversavano le cascate). Corretto anche un bug grave: 22 elementi non si muovevano per i giocatori (dischi, navette, ascensore, nastri e la molla del Laboratorio, senza la quale il Laboratorio non si finiva) | v46 |
| Interfaccia **moderna** (stile "Vetta Pop"): superfici lisce brillanti, pulsanti a pillola con bordo 3D, schede bianche, inchiostro blu notte, font **Nunito** (Heavy/ExtraBold/Bold) al posto di Denk One e Patrick Hand; anche la schermata di caricamento | v45 |
| Percorso Estremo: ingresso come **bivio all'inizio del sentiero normale** (ponticello in salita con arco a strisce dalla rampa, cartelli con la freccia sull'arco del sentiero e sulla rampa); **cascate** delle rapide rifatte come lastre sottili fra i livelli, con la schiuma che scende | v44 |
| Tolti lo striscione valanga "sei al sicuro" (in riparo, in vetta e nel Percorso Estremo non compare più) e il riquadro "Percorso Estremo 1/4" | v44 |
| PERCORSO ESTREMO: 4 sezioni (Rapide degli Abissi, Tempio del Deserto, Laboratorio dei Geni, Inferno), santuari con uovo Estremo e portale, muri invisibili, anti-cheat sul server, cronometro, missione settimanale | v40 |
| 12 pet Estremi (3 pesci degli abissi, 3 egizi, 3 felini geniali, 3 diavoli) e rarità Estremo con schiusa per sezione | v40 |
| 3 giganti galattici nel negozio (Leone Nebulosa 399, Kraken Stellare 599, Balena Cosmica 799 R$), non si rubano né si vendono | v40 |
| Tre troni per lotto: Trono 2 = 5 miliardi o 399 R$, Trono 3 = 50 miliardi o 799 R$ (isole fluttuanti) | v40 |
| Interni dell'interfaccia bianchi puri (niente crema) | v41 |
| Colori dell'interfaccia ancora più brillanti | v42 |
| Interfaccia meno "da AI": stile **"cucito"** (feltro dai colori accesi, cucitura bianca attaccata al contorno scuro, interni quasi bianchi, Denk One + Patrick Hand) | v36 |
| Popup (VALANGA, furti, annunci, nome della zona) spostati in alto sotto le monete; messaggi in basso a destra | v36 |
| Piazza della vetta: ruota della fortuna, missioni giornaliere e settimanali, re della collina | v35 |
| 10 mostri Primordiali (2 per zona) e uovo Primordiale | v35 |
| Tana dei Mostri: tunnel dal cratere con un uovo Ultra sempre presente | v33 |
| Scalino della piazza, animazione del martello, scritta dei soldi che entrava nel pavimento | v26 |
| Pacchetto dei pet e delle uova per un altro agente (`tools/export_pack.py`) | — |
