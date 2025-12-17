// const socket = io('http://localhost:5000');
const socket = io('https://president-ikcm.onrender.com');

// DOM Elements
const loginScreen = document.getElementById('login-screen');
const lobbyScreen = document.getElementById('lobby-screen');
const gameBoard = document.getElementById('game-board');
const usernameInput = document.getElementById('username');
const btnJoin = document.getElementById('btn-join');
const playersListUl = document.getElementById('players-list');
const btnStartGame = document.getElementById('btn-start-game');
const lobbyStatus = document.getElementById('lobby-status');
const playerCountSpan = document.getElementById('player-count-num');

const myHandDiv = document.getElementById('my-hand');
const tableArea = document.getElementById('table-area');
const statusMsg = document.getElementById('status-msg');
const myRoleDisplay = document.getElementById('my-role-display');
const btnPlay = document.getElementById('btn-play');
const btnPass = document.getElementById('btn-pass');
const btnExchange = document.getElementById('btn-exchange');
const exchangeArea = document.getElementById('exchange-area');
const opponentsContainer = document.getElementById('opponents-container');

let selectedCards = new Set();
let allPlayers = []; // Stocke la liste des pseudos
let myLastMove = null; // Track my last played cards
let myUsername = ""; // Mon pseudo

// --- LOGIN ---
btnJoin.addEventListener('click', () => {
    const username = usernameInput.value;
    if (username) {
        myUsername = username; // On stocke le pseudo
        socket.emit('join_game', { username: username });
        loginScreen.classList.add('hidden');
        lobbyScreen.classList.remove('hidden');
    }
});
// Trigger Login on Enter key
usernameInput.addEventListener("keypress", function (event) {
    if (event.key === "Enter") btnJoin.click();
});

// --- LOBBY ---
socket.on('update_player_list', (data) => {
    const players = data.players;
    allPlayers = players; // On met à jour la liste globale
    playersListUl.innerHTML = "";
    playerCountSpan.innerText = players.length;

    players.forEach(name => {
        const li = document.createElement('li');
        li.innerText = name;
        playersListUl.appendChild(li);
    });

    if (players.length >= 2) {
        btnStartGame.disabled = false;
        btnStartGame.innerHTML = "LANCER LA PARTIE 🚀";
        lobbyStatus.innerText = "Prêt à décoller !";
        lobbyStatus.style.color = "#4CAF50";
    } else {
        btnStartGame.disabled = true;
        btnStartGame.innerHTML = "EN ATTENTE...";
        lobbyStatus.innerText = "En attente d'adversaires...";
        lobbyStatus.style.color = "#ccc";
    }
});

btnStartGame.addEventListener('click', () => socket.emit('start_game_command'));
socket.on('game_started', () => {
    lobbyScreen.classList.add('hidden');
    gameBoard.classList.remove('hidden');
});

// --- GAME LOOP ---

function getCardFileName(cardCode) {
    let rankCode, suitCode;
    if (cardCode.length === 3) { rankCode = cardCode.slice(0, 2); suitCode = cardCode.slice(2); }
    else { rankCode = cardCode.slice(0, 1); suitCode = cardCode.slice(1); }

    const rankMap = { 'J': 'jack', 'Q': 'queen', 'K': 'king', 'A': 'ace' };
    const suitMap = { 'H': 'hearts', 'D': 'diamonds', 'C': 'clubs', 'S': 'spades' };
    const rankName = rankMap[rankCode] || rankCode;
    const suitName = suitMap[suitCode];
    return `${rankName}_of_${suitName}.png`;
}

socket.on('game_state', (state) => {
    console.log("State:", state);

    // Update UI Elements
    // Détection Ghost Cards (Pour les 2 ou Carrés qui vident instantanément)
    let ghostCards = null;

    // Si la table est vide MAIS que je viens de jouer (myLastMove existe),
    // c'est que mon coup a vidé la table (ex: j'ai mis un 2).
    // Le serveur renvoie table: [] tout de suite.
    if (state.table.length === 0 && myLastMove) {
        // On vérifie si c'est "moi" qui ai vidé ?
        // On suppose que oui si la réponse arrive juste après mon coup.
        // On utilisera myLastMove pour l'animation.
        ghostCards = myLastMove;
        myLastMove = null; // On consomme le move
    }

    // TODO: Gérer le cas des ADVERSAIRES (si le serveur envoyait 'last_played')
    // S'il y a state.last_played et que table est vide, on l'utilise
    if (state.table.length === 0 && state.last_played && !ghostCards) {
        ghostCards = state.last_played;
    }

    renderHand(state.hand, state.playable_mask, state.is_my_turn, state.is_exchange);
    renderTable(state.table, ghostCards);

    // Rendu des adversaires et surbrillance du tour
    // On essaie de deviner à qui c'est le tour via state.current_player (s'il existe)
    let activePlayerName = state.current_player;
    if (state.is_my_turn) activePlayerName = myUsername; // Fallback pour moi-même

    renderOpponents(allPlayers, activePlayerName);

    // Status text update
    statusMsg.innerHTML = state.message;

    // Role update
    if (state.my_role) {
        myRoleDisplay.innerText = state.my_role;
        // Couleur dynamique du badge selon le rôle
        if (state.my_role.includes("Président")) myRoleDisplay.style.borderColor = "#f1c40f";
        else if (state.my_role.includes("Trou")) myRoleDisplay.style.borderColor = "#8c7ae6";
        else myRoleDisplay.style.borderColor = "#fff";
    }

    // --- LOGIQUE BOUTONS ---
    if (state.is_exchange) {
        // ... (Code échange inchangé) ...
        btnPlay.parentElement.classList.add('hidden');
        exchangeArea.classList.remove('hidden');
        if (state.exchange_info) {
            btnExchange.classList.remove('hidden');
            btnExchange.innerText = `RENDRE ${state.exchange_info.count} CARTE(S)`;
            statusMsg.style.color = "#ff4757";
        } else { /* ... */ }

    } else {
        // Mode Jeu
        btnPlay.parentElement.classList.remove('hidden');
        exchangeArea.classList.add('hidden');

        // Est-ce que j'ai au moins une carte jouable dans ma main ?
        // (Le masque contient au moins un 'true')
        const hasPlayableCards = state.playable_mask && state.playable_mask.includes(true);

        if (state.is_my_turn) {
            statusMsg.style.color = "#f1c40f";
            statusMsg.style.textShadow = "0 0 10px rgba(241, 196, 15, 0.5)";

            // Ajout de l'effet visuel
            document.querySelector('.app-container').classList.add('my-turn-active');

            btnPlay.disabled = false;
            btnPass.disabled = false;

        } else {
            // CE N'EST PAS MON TOUR
            statusMsg.style.color = "#fff";
            statusMsg.style.textShadow = "none";

            // Retrait de l'effet visuel
            document.querySelector('.app-container').classList.remove('my-turn-active');

            // Le bouton PASSER est désactivé (on ne passe pas hors tour)
            btnPass.disabled = true;

            // NOUVEAU : Le bouton JOUER est actif SI j'ai une coupe possible (hasPlayableCards)
            if (hasPlayableCards) {
                btnPlay.disabled = false;
                btnPlay.innerText = "COUPER !"; // Petit feedback visuel sympa
                btnPlay.style.background = "linear-gradient(45deg, #ff5722, #f44336)"; // Rouge feu
            } else {
                btnPlay.disabled = true;
                btnPlay.innerText = "JOUER";
                btnPlay.style.background = ""; // Retour style normal
            }
        }
    }
});

function renderHand(cardsCodes, playableMask, isMyTurn, isExchange) {
    myHandDiv.innerHTML = "";
    selectedCards.clear();

    cardsCodes.forEach((code, index) => {
        const img = document.createElement('img');
        img.src = `assets/${getCardFileName(code)}`;
        img.className = 'card';

        let shouldDisable = false;

        if (isExchange) {
            shouldDisable = false;
        } else {
            // CORRECTION ICI :
            // On ne regarde plus 'isMyTurn'. 
            // On fait confiance au masque du serveur (playableMask).
            // Le serveur a déjà mis 'false' partout si ce n'est pas mon tour,
            // SAUF pour les cartes qui permettent de couper.

            if (playableMask && playableMask[index] === false) {
                shouldDisable = true;
            }
        }

        if (shouldDisable) {
            img.classList.add('disabled');
        } else {
            img.addEventListener('click', () => toggleCardSelection(img, code));
        }
        myHandDiv.appendChild(img);
    });
}

let tableClearTimeout = null;
let previousTableSize = 0; // Pour savoir si la table était pleine avant

function renderTable(cardsCodes, ghostCards = null) {
    // 1. Détection : Est-ce qu'on vient de nettoyer le pli ?
    // Condition : La table devient vide (0) ALORS QU'elle avait des cartes avant (>0)
    // OU BIEN : On a reçu des "ghostCards" (coup instantané type 2 ou Carré qui vide directement)
    const isClearingTrick = (cardsCodes.length === 0 && previousTableSize > 0) || (cardsCodes.length === 0 && ghostCards && ghostCards.length > 0);
    previousTableSize = cardsCodes.length; // Mise à jour pour la prochaine fois

    // 2. Si on nettoie le pli -> Animation
    if (isClearingTrick) {

        // Cas spécial : Instant Clear (Ghost Cards)
        // On doit D'ABORD les afficher pour qu'elles puissent s'envoler
        if (ghostCards && ghostCards.length > 0) {
            tableArea.innerHTML = ""; // On vide le placeholder éventuel
            const cluster = document.createElement('div');
            cluster.style.display = 'flex';
            cluster.style.justifyContent = 'center';

            ghostCards.forEach(code => {
                const img = document.createElement('img');
                img.src = `assets/${getCardFileName(code)}`;
                img.className = 'card';
                cluster.appendChild(img);
            });
            tableArea.appendChild(cluster);
        }

        const images = tableArea.querySelectorAll('img');

        // On applique la classe d'animation à toutes les cartes actuelles
        images.forEach(img => {
            img.classList.add('clearing-animation');
        });

        // On attend la fin de l'animation (500ms définie dans le CSS) avant de vider le DOM
        // Si un nouveau paquet arrive entre temps (ex: jeu très rapide), on annulera ce timeout
        if (tableClearTimeout) clearTimeout(tableClearTimeout);

        tableClearTimeout = setTimeout(() => {
            tableArea.innerHTML = ""; // Vrai nettoyage du DOM
            // On peut rajouter un placeholder vide si on veut
            tableArea.innerHTML = '<div class="empty-table-placeholder">Table vide</div>';
        }, 2000); // Durée synchro avec le CSS (1.5s délai + 0.5s anim)

        return; // On arrête là, on ne redessine pas "rien" tout de suite
    }

    // 3. Si ce n'est pas un nettoyage (c'est un nouveau coup ou une table déjà vide)
    // On annule tout nettoyage en attente pour afficher les nouvelles cartes immédiatement
    // 3. Si ce n'est pas un nettoyage (c'est un nouveau coup ou une table déjà vide)

    // Si une animation est en cours (tableClearTimeout actif)
    if (tableClearTimeout) {
        // Si la nouvelle table est vide, on laisse l'animation se terminer
        // (C'est juste une mise à jour de changement de joueur par exemple)
        if (cardsCodes.length === 0) {
            return;
        }

        // Par contre, si de nouvelles cartes sont jouées, on coupe l'animation
        // pour afficher les nouvelles tout de suite.
        clearTimeout(tableClearTimeout);
        tableClearTimeout = null;
    }

    // --- Rendu Standard (Code existant) ---
    tableArea.innerHTML = "";

    if (cardsCodes.length === 0) {
        tableArea.innerHTML = '<div class="empty-table-placeholder">Table vide</div>';
        return;
    }

    const cluster = document.createElement('div');
    cluster.style.display = 'flex';
    cluster.style.justifyContent = 'center';

    cardsCodes.forEach(code => {
        const img = document.createElement('img');
        img.src = `assets/${getCardFileName(code)}`;
        img.className = 'card';
        cluster.appendChild(img);
    });

    tableArea.appendChild(cluster);
}

function toggleCardSelection(imgElement, code) {
    if (imgElement.classList.contains('selected')) {
        imgElement.classList.remove('selected');
        selectedCards.delete(code);
    } else {
        imgElement.classList.add('selected');
        selectedCards.add(code);
    }
}

// Events Buttons
btnPlay.addEventListener('click', () => {
    if (selectedCards.size === 0) return alert("Sélectionnez au moins une carte !");
    const cardsToPlay = Array.from(selectedCards);
    myLastMove = cardsToPlay; // On mémorise ce qu'on vient de jouer
    socket.emit('play_cards', { cards: cardsToPlay });
});

btnPass.addEventListener('click', () => {
    socket.emit('play_cards', { cards: [] });
});

btnExchange.addEventListener('click', () => {
    if (selectedCards.size === 0) return alert("Sélectionnez les cartes à rendre !");
    socket.emit('give_cards_back', { cards: Array.from(selectedCards) });
});

function renderOpponents(players, currentPlayerName) {
    // Si la liste est vide (pas encore reçue), on ne fait rien
    if (!players || players.length === 0) return;

    opponentsContainer.innerHTML = "";

    players.forEach(name => {
        // Optionnel : ne pas s'afficher soi-même ? 
        // L'utilisateur a dit "ajoute les joueurs", souvent on veut aussi voir quand c'est son tour
        // Mais on a déjà "my-turn-active" sur l'écran. 
        // Affichons tout le monde pour la clarté.

        const div = document.createElement('div');
        div.className = 'opponent-profile';

        // Est-ce son tour ?
        if (currentPlayerName && name === currentPlayerName) {
            div.classList.add('active-turn');
        }

        div.innerHTML = `
            <div class="opponent-avatar">👤</div>
            <div class="opponent-name">${name}</div>
        `;
        opponentsContainer.appendChild(div);
    });
}

socket.on('notification', (data) => {
    console.log("Notif:", data.message);
    if (data.message.includes("Erreur")) alert(data.message);
    // Ici on pourrait ajouter un vrai système de Toast/Popup moderne
});