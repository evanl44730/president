// Connexion au serveur Python (assure-toi que le port 5000 est correct)
const socket = io('http://localhost:5000');

// --- SÉLECTION DES ÉLÉMENTS DU DOM ---

// Écrans (Vues)
const loginScreen = document.getElementById('login-screen');
const lobbyScreen = document.getElementById('lobby-screen');
const gameBoard = document.getElementById('game-board');

// Éléments Login
const usernameInput = document.getElementById('username');
const btnJoin = document.getElementById('btn-join');

// Éléments Lobby
const playersListUl = document.getElementById('players-list');
const btnStartGame = document.getElementById('btn-start-game');
const lobbyStatus = document.getElementById('lobby-status');

// Éléments Jeu
const myHandDiv = document.getElementById('my-hand');
const tableArea = document.getElementById('table-area');
const statusMsg = document.getElementById('status-msg');
const btnPlay = document.getElementById('btn-play');
const btnPass = document.getElementById('btn-pass');

// Variables d'état
let selectedCards = new Set(); // Stocke les codes des cartes sélectionnées (ex: "3H", "10D")


// ============================================================
// 1. PHASE DE CONNEXION (LOGIN)
// ============================================================

btnJoin.addEventListener('click', () => {
    const username = usernameInput.value;
    if (username) {
        // Envoie la demande de rejoindre au serveur
        socket.emit('join_game', { username: username });
        
        // Transition UX : On cache le login, on affiche le lobby
        loginScreen.classList.add('hidden');
        lobbyScreen.classList.remove('hidden');
    }
});


// ============================================================
// 2. PHASE DE LOBBY (SALLE D'ATTENTE)
// ============================================================

// Mise à jour de la liste des joueurs connectés
socket.on('update_player_list', (data) => {
    const players = data.players;
    
    // Vider la liste actuelle
    playersListUl.innerHTML = "";
    
    // Remplir avec les nouveaux noms
    players.forEach(name => {
        const li = document.createElement('li');
        li.innerText = name;
        playersListUl.appendChild(li);
    });

    // Gestion de l'activation du bouton "Lancer"
    if (players.length >= 2) {
        btnStartGame.disabled = false;
        btnStartGame.style.backgroundColor = "#ffcc00"; // Jaune actif
        btnStartGame.style.cursor = "pointer";
        lobbyStatus.innerText = "Prêt à lancer la partie !";
        lobbyStatus.style.color = "#4CAF50"; // Vert
    } else {
        btnStartGame.disabled = true;
        btnStartGame.style.backgroundColor = "#ccc"; // Gris désactivé
        btnStartGame.style.cursor = "not-allowed";
        lobbyStatus.innerText = "En attente d'au moins 2 joueurs...";
        lobbyStatus.style.color = "#FF9800"; // Orange
    }
});

// Action : Cliquer sur "Lancer la partie"
btnStartGame.addEventListener('click', () => {
    socket.emit('start_game_command');
});

// Réception du signal de démarrage du jeu
socket.on('game_started', () => {
    // Transition UX : On cache le lobby, on affiche le tapis de jeu
    lobbyScreen.classList.add('hidden');
    gameBoard.classList.remove('hidden');
});


// ============================================================
// 3. PHASE DE JEU (GAME LOOP)
// ============================================================

// --- A. Fonctions Utilitaires ---

// Convertit le code serveur (ex: "10H") vers le nom de fichier (ex: "10_of_hearts.png")
function getCardFileName(cardCode) {
    // Cas particulier du "10" qui fait 2 caractères
    // Si la carte a 3 caractères (ex "10H"), le rang est les 2 premiers. Sinon c'est le 1er.
    let rankCode, suitCode;
    
    if (cardCode.length === 3) {
        rankCode = cardCode.slice(0, 2); // "10"
        suitCode = cardCode.slice(2);    // "H"
    } else {
        rankCode = cardCode.slice(0, 1); // "K"
        suitCode = cardCode.slice(1);    // "D"
    }

    const rankMap = {
        'J': 'jack',
        'Q': 'queen',
        'K': 'king',
        'A': 'ace'
        // Les chiffres (3, 4... 10, 2) restent tels quels
    };

    const suitMap = {
        'H': 'hearts',
        'D': 'diamonds',
        'C': 'clubs',
        'S': 'spades'
    };

    const rankName = rankMap[rankCode] || rankCode; 
    const suitName = suitMap[suitCode];

    return `${rankName}_of_${suitName}.png`;
}


// --- B. Gestion de l'état du jeu (Réception du serveur) ---

socket.on('game_state', (state) => {
    console.log("État du jeu reçu :", state);

    // 1. Mettre à jour ma main
    renderHand(state.hand);

    // 2. Mettre à jour la table (cartes posées)
    renderTable(state.table);

    // 3. Mettre à jour les messages d'info
    statusMsg.innerText = state.message;

    btnPlay.disabled = false; 
    btnPass.disabled = !state.is_my_turn;
    btnPlay.classList.remove('disabled');
    
    // 4. Activer/Désactiver les boutons selon si c'est mon tour
    if (state.is_my_turn) {
        statusMsg.style.color = "#ffcc00"; 
        statusMsg.innerText += " (C'est à TOI !)";
        // On peut passer seulement si c'est notre tour
        btnPass.disabled = false; 
    } else {
        statusMsg.style.color = "white";
        statusMsg.innerText += " (Tu peux couper si tu as les mêmes cartes)";
        // On ne peut PAS passer si ce n'est pas notre tour
        btnPass.disabled = true; 
    }
});

// --- C. Fonctions d'affichage ---

function renderHand(cardsCodes) {
    myHandDiv.innerHTML = ""; // On efface l'ancienne main
    selectedCards.clear();    // On réinitialise la sélection à chaque tour pour éviter les bugs

    cardsCodes.forEach((code, index) => {
        const img = document.createElement('img');
        img.src = `assets/${getCardFileName(code)}`;
        img.className = 'card';
        img.alt = code;
        
        // Gestion du clic sur une carte
        img.addEventListener('click', () => toggleCardSelection(img, code));
        
        myHandDiv.appendChild(img);
    });
}

function renderTable(cardsCodes) {
    tableArea.innerHTML = ""; // On efface la table
    
    if (cardsCodes.length === 0) return; // Si table vide, on ne fait rien

    // Création d'un conteneur pour centrer les cartes
    const cluster = document.createElement('div');
    cluster.style.display = 'flex';
    cluster.style.justifyContent = 'center';
    cluster.style.gap = '10px'; // Espace entre les cartes posées

    cardsCodes.forEach(code => {
        const img = document.createElement('img');
        img.src = `assets/${getCardFileName(code)}`;
        // Style spécifique pour les cartes sur la table (plus petites, pas de pointeur)
        img.style.width = '90px'; 
        img.style.height = 'auto';
        img.style.borderRadius = '5px';
        img.style.boxShadow = '0 4px 8px rgba(0,0,0,0.3)';
        
        cluster.appendChild(img);
    });

    tableArea.appendChild(cluster);
}

// --- D. Gestion des interactions ---

function toggleCardSelection(imgElement, code) {
    // Bascule la classe CSS "selected" et ajoute/retire du Set
    if (imgElement.classList.contains('selected')) {
        imgElement.classList.remove('selected');
        selectedCards.delete(code);
    } else {
        imgElement.classList.add('selected');
        selectedCards.add(code);
    }
}

// Bouton JOUER
btnPlay.addEventListener('click', () => {
    if (selectedCards.size === 0) {
        alert("Vous devez sélectionner au moins une carte !");
        return;
    }
    // Convertit le Set en tableau pour l'envoi JSON
    const cardsArray = Array.from(selectedCards);
    socket.emit('play_cards', { cards: cardsArray });
});

// Bouton PASSER
btnPass.addEventListener('click', () => {
    // Passer revient à jouer une liste vide
    socket.emit('play_cards', { cards: [] });
});

// Gestion des erreurs/notifications
socket.on('notification', (data) => {
    // Affiche une alerte ou log en console
    if(data.message.includes("Erreur")) {
        alert(data.message); // Alerte pour les erreurs de règles (ex: carte trop faible)
    } else {
        console.log("Info:", data.message);
    }
});