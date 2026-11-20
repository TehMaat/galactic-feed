# Novità

Tutte le versioni di Galactic Feed, dalla più recente. I numeri seguono [semver](https://semver.org/lang/it/): `MAGGIORE.MINORE.CORRETTIVA`. Finché la versione comincia con `0.` l'app è giovane: le novità arrivano con le versioni minori (0.4, 0.5…), le correzioni con le correttive (0.3.1).

Per aggiornare basta scaricare la nuova immagine: le modifiche al database si applicano da sole all'avvio. Prima di saltare a una nuova versione minore conviene fare una copia del volume `/data` (vedi [Aggiornare e backup](docs/aggiornare-e-backup.md)).

## [0.15.1] – 2026-11-20

### Correzioni
- **«Impostazioni» nel Profilo** (#81): sul telefono e sul tablet porta alle sezioni delle Impostazioni più in basso nel Profilo invece di aprire la pagina con la ricerca. Sul computer apre la pagina come prima.
- La ricerca nelle impostazioni prende il cursore solo quando tocchi «Cerca nelle impostazioni» (#81). Prima, dopo averla usata una volta, la tastiera si riapriva a ogni apertura delle Impostazioni.

## [0.15.0] – 2026-11-20

### Novità
- **Statistiche per settimana, mese, anno o di sempre** (#83): nel Profilo il periodo si sceglie tra quattro voci. Sull'anno il grafico dei letti va per mese; «di sempre» parte dal primo articolo aperto o salvato e va per giorno, per mese o per anno secondo quanto tempo è passato.

### Correzioni
- Nel Profilo sul telefono «Amministrazione» non riempie più tutto il riquadro (#82): il testo delle scorciatoie scende un po' sugli schermi stretti e, se non ci sta, finisce con i puntini.

### Da sapere per aggiornare
- Il `docker-compose.yml` d'esempio ora usa `:0.15`: chi ha `:0.14` deve cambiare il numero per ricevere le novità (con `:0.14` arrivano solo le correzioni della 0.14).

## [0.14.1] – 2026-11-20

### Correzioni
- **La barra «Cerca nelle impostazioni» non esce più dallo schermo** (#84): sui telefoni stretti o con il testo ingrandito era più larga della pagina; ora resta nei margini come le card.
- **Vetro uguale ovunque** (#85): barre, pillole, card, Edizioni, gruppi delle impostazioni, sheet e lettore usano lo stesso fondo e la stessa sfocatura della Dock. La barra di ricerca delle impostazioni e le pillole in alto non lasciano più leggere il testo che ci scorre sotto.

## [0.14.0] – 2026-11-20

### Novità
- **Edizioni più grandi delle notizie** (#80): in Oggi la card di un'Edizione ha la copertina a tutta larghezza, più alta della foto delle notizie, con il nome grande sopra la foto, l'etichetta delle regole, «X da leggere», la data e quante notizie ha; sotto il titolo d'apertura. Prima era una riga con una miniatura, più piccola delle notizie, e l'occhio andava sul Notiziario. Stesso formato su telefono, tablet e computer; un'Edizione già letta ha la foto spenta, come le notizie lette.

### Da sapere per aggiornare
- Il `docker-compose.yml` d'esempio ora usa `:0.14`: chi ha `:0.13` deve cambiare il numero per ricevere le novità (con `:0.13` arrivano solo le correzioni della 0.13).

## [0.13.0] – 2026-11-19

### Novità
- **Nuovo aspetto in vetro sul telefono** (#64): superfici trasparenti e sfocate sopra aloni di colore, una barra in alto con il nome dell'app e la data, e una Dock a pillola che galleggia in basso con **Oggi · Notiziario · Cerca · Profilo**. Fonti, Interessi, Salvati, Impostazioni e Amministrazione si aprono dal Profilo. Spazi e allineamenti seguono una scala sola.
- **Oggi con Edizioni e Notiziario nello stesso scroll** (#64): in alto le Edizioni di oggi (etichetta, nome, data, quante notizie ha e titolo d'apertura), sotto il Notiziario. Un'Edizione si apre come un articolo; «Indietro» dall'articolo torna all'Edizione. Senza Edizioni c'è solo il Notiziario e la Dock non ha la voce «Notiziario». Lo swipe tra Edizione e Flusso (#29) non serve più ed è stato tolto.
- **Il Flusso si chiama Notiziario** (#77), con un'icona nuova: righe di notizie con un punto «in diretta». Le icone sono un po' più marcate (#72).
- **Computer** (#65): barra in vetro con le sezioni, «Cerca», Impostazioni, Amministrazione e il tuo avatar; a sinistra Edizioni e Notiziario, a destra l'articolo o l'Edizione aperta. Il Profilo è una pagina larga con le statistiche.
- **Card delle notizie con la foto grande** (#70): sopra la foto a tutta larghezza con il titolo e la fonte in alto a destra, sotto l'estratto e «salva». Niente più tempo di lettura, etichette e ore sulle card; nell'articolo aperto l'ora di pubblicazione è in alto a destra, accanto alla fonte.
- **«X notizie · X da leggere»** (#66) sotto il titolo del Notiziario e in Cerca: segue il filtro e scende mentre leggi.
- **Filtri a inclusione ed esclusione e preset** (#68): sulla riga del Notiziario ci sono solo i preset (Per te, Tutte, Non letti e quelli che crei tu), con sfumatura e freccia quando non ci stanno. Nel pannello **Filtri** interessi (tag e gruppi di parole), video, cartelle, nazioni e fonti si possono nascondere o tenere da soli; i filtri si salvano come preset con un nome e restano anche chiudendo l'app.
- **Preset all'apertura** (#69): in Impostazioni → Lettura o nei Filtri scegli da quale preset parte il Notiziario; se non scegli niente, «Per te». Con «Per te» ancora vuoto l'app lo dice e propone di scegliere gli interessi.
- **Cerca** è una sezione a parte, negli articoli e nei nomi delle fonti.
- **Ricerca nelle impostazioni** (#67): filtra le voci sul posto, evidenzia la parola e capisce qualche sinonimo («dark», «token», «password»). Sul telefono sparisce scorrendo verso il basso e torna risalendo; sul computer sta nella colonna a sinistra.
- **Palette Solarized** (#73), scura e chiara, tra le varianti dei temi.
- **Colore personalizzato** (#74): l'ultimo pallino dei colori apre il selettore; l'app adatta il colore perché si legga in chiaro e in scuro. I colori stanno su una riga sola.
- **Un solo font** (#75) per interfaccia e articoli: Galactic (titoli in Plus Jakarta Sans, testo in Inter, articoli in Newsreader), Classico, Inter, Sistema, Alta leggibilità.
- **Nome e avatar** (#76): dal Profilo o da Impostazioni → Account cambi il nome e scegli una foto o le iniziali su un colore.
- **Statistiche nel Profilo** (#78), su 7 o 30 giorni: articoli letti, salvati, giorni di fila, letti al giorno, interessi e fonti più letti, ore in cui leggi ed Edizioni aperte.

### Da sapere per aggiornare
- Una migrazione del database (avatar, articoli aperti per le statistiche, Edizioni aperte) si applica da sola all'avvio. Le statistiche contano gli articoli aperti da questa versione in poi.
- Chi aveva scelto un font per il «Testo degli articoli» ora ha lo stesso font per interfaccia e articoli: quello scelto in «Font».
- Il `docker-compose.yml` d'esempio ora usa `:0.13`: chi ha `:0.12` deve cambiare il numero per ricevere le novità (con `:0.12` arrivano solo le correzioni della 0.12).

## [0.12.1] – 2026-11-16

### Correzioni
- Il selettore **Edizione / Flusso** in Oggi è di nuovo allineato a ricerca, filtri e articoli. Sul computer con l'articolo a pagina intera e sul tablet in orizzontale partiva dal bordo sinistro invece di stare nella colonna centrata (#60).

## [0.12.0] – 2026-11-16

### Novità
- **Dock con la sezione attiva evidenziata**: su telefono e tablet una capsula tenue nel colore principale sta sotto il tasto della sezione aperta e scivola, con un piccolo rimbalzo, quando cambi sezione. In Fonti, Impostazioni e Amministrazione non c'è.

### Da sapere per aggiornare
- Nessuna migrazione del database.
- Il `docker-compose.yml` d'esempio ora usa `:0.12`: chi ha `:0.11` deve cambiare il numero per ricevere le novità (con `:0.11` arrivano solo le correzioni della 0.11).

## [0.11.0] – 2026-11-15

### Novità
- **Lettura più pulita** (#9): in alto restano solo Indietro, Salva e «⋯». Nel menu «⋯» ci sono la dimensione del testo (tre pulsanti, con quella in uso evidenziata), Condividi (dove il dispositivo lo permette), Apri l'originale e Segna come non letto. In fondo all'articolo c'è un solo pulsante, «Leggi su …». Scorrendo verso il basso la barra del lettore esce dallo schermo e rientra tornando su; una riga sottile in alto mostra quanto hai letto.
- **Articolo a pagina intera sul computer** (#9): in Impostazioni → Lettura scegli se l'articolo sta accanto all'elenco (come prima) o si apre a pagina intera sopra l'elenco, che allora usa tutta la larghezza. «Indietro» o Esc riportano all'elenco.
- **Dock con tre tasti**: su telefono e tablet la Dock ha Oggi, Interessi e Salvati. Le fonti si aprono da Impostazioni → Fonti, con «Indietro» per tornare. Sul computer Fonti resta nella barra in alto.

### Da sapere per aggiornare
- Nessuna migrazione del database.
- Il `docker-compose.yml` d'esempio ora usa `:0.11`: chi ha `:0.10` deve cambiare il numero per ricevere le novità (con `:0.10` arrivano solo le correzioni della 0.10).

## [0.10.0] – 2026-11-15

### Novità
- **Swipe tra Edizione e Flusso** (#29): in Oggi, sul telefono e sul tablet, con l'Edizione accesa si passa al Flusso scorrendo il dito verso sinistra e si torna all'Edizione verso destra. Il contenuto segue il dito; uno swipe corto torna al suo posto. Il gesto «indietro» dal bordo dello schermo, lo scorrimento delle chip dei filtri e il tasto Indietro funzionano come prima, e ognuna delle due ricorda dove eri arrivato.
- **L'app installata si aggiorna da sola** (#41): cerca la versione nuova quando la riapri e ogni ora. Se la trova appena riaperta e non stai leggendo, si ricarica da sola; altrimenti in basso compare «È disponibile una nuova versione» con **Aggiorna**. Non serve più togliere e riaggiungere l'app alla schermata Home (serve solo per vedere icona e nome nuovi).
- **Impostazioni → Informazioni**: versione dell'app (e del server, se diversa) e «Cerca aggiornamenti».

### Correzioni
- Due impostazioni cambiate una subito dopo l'altra (per esempio «AI» e poi «Salva la descrizione» negli Interessi) potevano annullarsi: la seconda riportava la prima al valore di prima. Ora si salvano tutte e due.

### Da sapere per aggiornare
- Nessuna migrazione del database.
- Il `docker-compose.yml` d'esempio ora usa `:0.10`: chi ha `:0.9` deve cambiare il numero per ricevere le novità (con `:0.9` arrivano solo le correzioni della 0.9).
- Il passaggio a questa versione è l'ultimo che può richiedere di chiudere del tutto e riaprire l'app installata; dalle successive arriva l'avviso «Aggiorna».

## [0.9.0] – 2026-11-15

### Novità
- **Barra di navigazione in alto sul computer**: il nome dell'app, le sezioni e, a destra, Impostazioni e Amministrazione stanno in un'unica barra in alto, al posto della colonna a sinistra. La lista e l'articolo si allargano.
- **Il tablet è come il telefono**: barra in alto con il nome dell'app e le Impostazioni, Dock fluttuante in basso con le sezioni, e le due barre escono dallo schermo scorrendo verso il basso (#36). Scorre la pagina, così nel browser si riduce anche la barra degli indirizzi (#38). L'Amministrazione si apre dalle Impostazioni, come sul telefono.
- **Come funzionano i doppioni**: un cerchio con la «i», accanto a «Unisci i doppioni» in Interessi e accanto ad «Anche su» nell'articolo, spiega quando due articoli sono la stessa notizia, quale si vede (il primo pubblicato tra quelli che passano i filtri) e che letto e non letto valgono per tutte le versioni.

### Correzioni
- **Colore del sistema** (#46): il campione in Impostazioni → Aspetto mostra il colore che arriva davvero, e la nota dice la verità. Chrome, Edge e i telefoni Android non fanno conoscere il colore del sistema e danno sempre lo stesso blu; prima la nota diceva che il colore veniva dalle impostazioni del dispositivo. Il colore del sistema ora viene scurito in chiaro e schiarito in scuro quanto basta perché testo e pulsanti si leggano bene (contrasto AA, come gli altri colori); prima si usava così com'era, anche dove non si leggeva.
- **Font** (#46): «Galactic» usa il font del dispositivo per tutto tranne i titoli anche su Linux e ChromeOS (prima Roboto o Arial); «Sistema» lo usa anche per i titoli. La nota spiega che sui telefoni Android il browser usa Roboto e non i font scelti nelle impostazioni del telefono.

### Da sapere per aggiornare
- Nessuna migrazione del database.
- Il `docker-compose.yml` d'esempio ora usa `:0.9`: chi ha `:0.8` deve cambiare il numero per ricevere le novità (con `:0.8` arrivano solo le correzioni della 0.8).

## [0.8.0] – 2026-11-15

### Novità
- **Tutto schermo anche nel browser del telefono** (#38): aprendo Galactic Feed in Safari o Chrome, senza installarlo, scorrendo verso il basso si riduce anche la barra degli indirizzi. Ogni sezione ricorda dove eri arrivato, anche dopo aver letto un articolo o usato il tasto Indietro; con un articolo o una scheda aperti la lista sotto resta ferma. Nel browser non c'è più il «tira giù per aggiornare» (c'è il pulsante Aggiorna). Su tablet, computer e nell'app installata non cambia niente.
- **Più spazio per leggere sul telefono** (#36): scorrendo verso il basso la barra in alto e quella delle sezioni escono dallo schermo; appena torni su, anche di poco, rientrano. Ricompaiono anche in cima e in fondo all'elenco, cambiando sezione e chiudendo un articolo. La barra delle sezioni è diventata una Dock fluttuante: staccata dal fondo e dai lati, con gli angoli arrotondati e più trasparente. Su tablet e computer non cambia niente.
- **Nascondi gli articoli senza testo completo** (#32): in Impostazioni → Lettura. Alcuni siti mettono nel feed solo un estratto e non lasciano leggere la pagina (paywall, blocchi); con l'opzione accesa i loro articoli non compaiono nel Flusso, nell'Edizione, nei contatori e nelle notifiche. I salvati restano, gli articoli appena arrivati si vedono subito mentre il server prova a scaricare il testo completo, e se la stessa notizia arriva anche da una fonte che la dà intera si mostra quella. Nel Flusso un avviso dice quanti articoli sono nascosti e li mostra con un tocco; la scheda della fonte dice «Spesso solo estratto» quando il sito di solito non lascia leggere. È anche tra i predefiniti per i nuovi utenti, in Amministrazione.
- **Nuova icona per iPhone e iPad**, nello stile delle icone Apple: sfondo nero pulito, con l'anello e il pianeta, che sta bene sia sulla Home chiara sia su quella scura (#30, #40). iOS salva l'icona quando aggiungi l'app alla schermata Home: per vedere quella nuova togli l'app dalla Home e aggiungila di nuovo.
- **Le cartelle delle fonti hanno la matita**: in Fonti, accanto al nome di ogni cartella, una matita indica che toccandola si cambiano nome e colore o si elimina la cartella (#33). Prima il nome sembrava una semplice etichetta.

### Correzioni
- Sul telefono le barre sparivano quasi di colpo scorrendo giù; ora escono con lo stesso movimento con cui entrano, al contrario: partono piano, accelerano e svaniscono alla fine.
- Modificare una cartella non funzionava: il nome scritto tornava subito quello di prima e «Salva» lasciava tutto com'era (#33).
- Notifiche: dalla seconda in poi con lo stesso argomento (per esempio la notifica di prova ripetuta) sostituivano in silenzio quella ancora nel centro notifiche, senza banner né suono, e sembravano non arrivare. Ora ogni notifica si vede.
- Notifiche: la prova va solo al dispositivo da cui la chiedi e, se il servizio push (Apple, Google, Mozilla, Microsoft) la rifiuta, il messaggio dice il motivo; prima bastava che arrivasse a un altro dispositivo per dire «inviata». Gli errori finiscono anche nel log del server.
- Notifiche: aprendo le Impostazioni il dispositivo si riiscrive da solo se il server lo aveva dimenticato o se l'iscrizione era stata fatta con chiavi del server ormai cambiate (per esempio dopo aver ricreato il volume `/data`); prima l'interruttore restava acceso ma non arrivava più nulla.

### Da sapere per aggiornare
- Nessuna migrazione del database.
- Il `docker-compose.yml` d'esempio ora usa `:0.8`: chi ha `:0.7` deve cambiare il numero per ricevere le novità (con `:0.7` arrivano solo le correzioni della 0.7).
- L'app installata sul telefono passa alla nuova versione alla riapertura: se mostra ancora la vecchia, chiudila del tutto e riaprila.

## [0.7.0] – 2026-11-07

### Novità
- **Impostazioni e Amministrazione sono pagine** (`/impostazioni`, `/amministrazione`) invece di finestre: sul computer occupano tutta la larghezza, con l'indice delle sezioni a sinistra; sul telefono si aprono come le altre sezioni.
- **Varianti del tema**: lo scuro può essere Notte (blu, come prima), Grigio o Nero (per gli schermi OLED); il chiaro Neutro o Carta (toni caldi). Si scelgono in Impostazioni → Aspetto e tra i predefiniti per i nuovi utenti.
- **Accesso con OIDC ha la sua voce** in Amministrazione (prima era in fondo a «Accesso», insieme alla durata delle sessioni), con lo stato a colpo d'occhio. Nell'elenco degli utenti si vede chi entra con la password, chi con il provider e chi con entrambi.
- Un'uscita di un'Edizione (per esempio una composta per prova) si elimina da Oggi, con «Elimina questa uscita»; da lì si apre anche la scheda dell'Edizione. Nelle Impostazioni ogni Edizione ha il suo pulsante per eliminarla.

### Correzioni
- Eliminare un'Edizione (e una cartella, un tag, una fonte, un gruppo, un utente) a volte non faceva niente: la conferma era quella del browser, che alcune app installate e alcuni browser non mostrano. Ora la conferma è una finestra dell'app.
- L'accesso con OIDC affianca gli account locali e non li sostituisce: il collegamento automatico (stessa email o stesso nome utente) non tocca mai un amministratore, così l'amministratore locale resta un account a parte con la sua password.
- Un utente del provider reso amministratore a mano resta amministratore: il gruppo del provider toglie solo i permessi che ha dato lui.

### Da sapere per aggiornare
- Migrazione automatica `012`.
- Il `docker-compose.yml` d'esempio ora usa `:0.7`: chi ha ancora `:0.5` o `:0.6` deve cambiare il numero per ricevere le novità.

## [0.6.0] – 2026-11-07

### Novità
- **Accesso con un provider OpenID Connect** (Authentik, Authelia, Keycloak, Pocket ID…), configurato e provato tutto dall'app in Amministrazione → Accesso: pulsante «Entra con …», utenti creati al primo accesso o collegati per email verificata o nome utente, account collegati nelle Impostazioni, amministratori da un gruppo del provider, uscita anche dal provider (#22).
- Il login con password si può spegnere, con un accesso d'emergenza sempre disponibile: `python -m app.emergency` nel container o `EMERGENCY_PASSWORD_LOGIN=true`.
- Chi è entrato con il provider può scegliersi anche una password.

### Sicurezza
- Flusso authorization code con PKCE, `state` e `nonce`; l'ID token si verifica con le chiavi del provider. Il client secret è salvato cifrato e non viene mai mostrato.

### Da sapere per aggiornare
- Migrazione automatica `011`.
- Nuova dipendenza: PyJWT.
- Il `docker-compose.yml` d'esempio ora usa `:0.6`.

## [0.5.0] – 2026-11-07

Prima versione pubblicata come release: immagini `ghcr.io/tehmaat/galactic-feed:0.5.0` e `:0.5`. Contiene anche le novità di 0.3.0 e 0.4.0.

### Novità
- **Gruppi di parole** pronti e personali per interessi e parole silenziate (Motori, Politica, Tecnologia, Calcio…): si accendono con un tocco come interesse o per silenziare, se ne cambiano le parole, se ne creano di nuovi. La corrispondenza mostra il gruppo («Tecnologia · iPhone»). L'amministratore gestisce i gruppi pronti (#16).
- **Tag delle fonti**: proposti in automatico quando aggiungi una fonte, modificabili dalla scheda della fonte, usati come chip nel Flusso; gestione dei tag (rinomina, colore, ordine, unisci, elimina). Le tue scelte non vengono mai annullate (#17).
- **Più Edizioni**, ognuna con nome, regole (tag, cartelle, nazioni, gruppi di parole), numero massimo di notizie, periodo coperto e notifica; anteprima delle notizie e selettore in Oggi (#18).
- **Edizioni settimanali e mensili**: giorni della settimana, un giorno del mese o «il primo lunedì del mese», a uno o più orari, nel tuo fuso orario (#19).
- **Nazione delle fonti**, proposta dal dominio e dalla lingua: si sceglie per sé, l'amministratore la corregge per tutti; filtro nelle Fonti e nel Flusso, regola delle Edizioni (#20).

### Correzioni
- La scheda della fonte tornava ai dati iniziali dopo ogni modifica (icona, tag).

### Da sapere per aggiornare
- Migrazioni automatiche `008`–`010`.
- L'Edizione di prima diventa «La mia Edizione», con gli stessi orari e numeri. Si gestisce in Impostazioni → Edizioni.
- Il `docker-compose.yml` d'esempio ora usa `:0.5` invece di `:latest`.

## [0.4.0] – 2026-11-07

Non pubblicata come release: le sue novità escono con la 0.5.0, la prima con le immagini numerate.

### Novità
- **Pannello di amministrazione**: nella barra laterale sotto Impostazioni (sul telefono dentro le Impostazioni), solo per gli amministratori. Ci sono utenti e inviti, accesso, fonti e archivio, AI, predefiniti per i nuovi utenti e stato del sistema. Ogni impostazione dell'istanza si cambia dall'app senza riavviare; mostra se il valore è scelto lì, viene da una variabile d'ambiente o è il predefinito (#21).
- Nuove impostazioni da GUI: per quanto tenere gli articoli, intervallo proposto per le fonti nuove, fonti della rete locale sì/no, validità dei link d'invito, fuso orario dell'istanza.
- **Predefiniti per i nuovi utenti**: tema, colore, font, dimensione del testo, doppioni, riassunti, Edizione e orari.
- **Stato del sistema**: versione, spazio del database, ultimo controllo dei feed, feed con errori, ultimo errore dell'AI, variabili che valgono solo all'avvio.
- **Release automatiche**: quando su `main` arriva un numero nuovo in `VERSION`, il workflow pubblica le immagini `:X.Y.Z` e `:X.Y` e crea da solo il tag e la release su GitHub con le note di questo registro.

### Sicurezza
- La chiave dell'AI è salvata cifrata con `data/secret.key`; quella già salvata in chiaro si cifra da sola all'avvio.

### Correzioni
- Sul computer, nelle schede delle Impostazioni, il pulsante «Indietro» era invisibile.

### Da sapere per aggiornare
- Utenti, inviti e AI non sono più nelle Impostazioni personali ma in Amministrazione.
- Nuova variabile d'ambiente facoltativa `INVITE_HOURS`.
- **Copia di `data/secret.key`**: d'ora in poi serve anche per leggere la chiave dell'AI; se va persa, la chiave va reinserita.

## [0.3.0] – 2026-11-06

Non pubblicata come release: le sue novità escono con la 0.5.0, la prima con le immagini numerate.

### Novità
- **Icone dei giornali** al posto delle iniziali: favicon del sito o avatar del canale YouTube, trovate in automatico, anche offline. Dalla scheda della fonte si aggiornano, si sostituiscono con un'altra immagine o si tolgono (#11).
- **«Ricordami»** al login. Senza, chiudendo il browser si esce e la sessione finisce dopo 12 ore senza usare l'app; con, dura 90 giorni. L'amministratore sceglie le durate in Impostazioni → Accesso (#12).
- **Colore principale** a scelta tra otto, con contrasto verificato in chiaro e in scuro, oppure quello del sistema dove il browser lo permette (#14).
- **Font** dell'interfaccia (Galactic, Sistema, Inter, Alta leggibilità) e del testo degli articoli; dimensione del testo anche in Impostazioni → Aspetto (#15).
- Il **logo** «galactic feed» riporta a Oggi (#13).
- **Versioni**: numero unico nel file `VERSION` e questo registro delle novità.

### Correzioni
- La foto principale non compare più due volte aprendo un articolo (#10).

### Da sapere per aggiornare
- Migrazione automatica `007`: sessioni, icone delle fonti.
- Nuove variabili d'ambiente facoltative: `REMEMBER_DAYS`, `SESSION_HOURS`.

## [0.2.0] – 2026-11-03

Non pubblicata come release (immagine solo come `latest`). PR #8.

### Novità
- **Edizione**: una selezione delle notizie per te, composta agli orari che scegli.
- **AI** facoltativa, locale (Ollama) o cloud (Anthropic, OpenAI): sceglie le notizie e scrive riassunti in tre punti.
- **Notifiche push** per le categorie importanti e numero di non letti sull'icona dell'app.

## [0.1.0] – 2026-11-02

Prima versione. Non pubblicata come release (immagine solo come `latest`). PR #3–#7.

### Novità
- Account multiutente: primo avvio con codice nel log, inviti, link per una nuova password.
- Fonti RSS, Atom e canali YouTube, con ricerca automatica del feed, cartelle e OPML.
- Flusso con filtri, ricerca, interessi, parole silenziate e doppioni uniti; testo completo estratto dalla pagina.
- PWA per telefono, tablet e computer, con lettura offline di salvati e letti.
- Un solo container Docker per amd64, arm64 e armv7.
