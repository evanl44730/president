import eventlet
import socketio
from game_engine import Game, Card
from player import Player

sio = socketio.Server(cors_allowed_origins='*')
app = socketio.WSGIApp(sio)

game = Game()
sid_to_player = {}

def broadcast_player_list():
    """Envoie la liste des pseudos connectés à tout le monde (pour le lobby)"""
    usernames = [p.name for p in game.players]
    sio.emit('update_player_list', {'players': usernames})

def broadcast_game_state():
    for sid, player in sid_to_player.items():
        table_cards = [str(c) for c in game.current_trick]
        hand_cards = [str(c) for c in player.hand]
        
        # --- NOUVEAU : Calcul des cartes jouables ---
        # On calcule le masque pour ce joueur précis
        playable_mask = game.get_playable_mask(player)
        # --------------------------------------------

        current_player_name = game.players[game.current_player_index].name
        is_my_turn = (player == game.players[game.current_player_index])

        state = {
            "hand": hand_cards,
            "playable_mask": playable_mask, # On l'ajoute au JSON
            "table": table_cards,
            "current_player": current_player_name,
            "is_my_turn": is_my_turn,
            "message": f"C'est au tour de {current_player_name}"
        }
        
        # Info supplémentaire si on est bloqué
        if is_my_turn and game.forced_rank_active:
             state["message"] += " (BLOQUÉ : Tu suis ou tu passes !)"

        sio.emit('game_state', state, to=sid)

@sio.event
def connect(sid, environ):
    print(f"Client connecté : {sid}")

@sio.event
def disconnect(sid):
    if sid in sid_to_player:
        player = sid_to_player[sid]
        # Pour le MVP lobby, on retire le joueur s'il part avant le début
        if player in game.players:
            game.players.remove(player)
        del sid_to_player[sid]
        broadcast_player_list() # Mettre à jour la liste des présents

@sio.on('join_game')
def handle_join(sid, data):
    username = data.get('username', f"Joueur_{sid[:4]}")
    new_player = Player(username, sid)
    
    game.add_player(new_player)
    sid_to_player[sid] = new_player
    
    sio.emit('notification', {'message': f"Bienvenue {username}"}, to=sid)
    
    # Au lieu de démarrer, on envoie la liste mise à jour à tout le monde
    broadcast_player_list()

@sio.on('start_game_command')
def handle_start_game(sid):
    """Lancé quand un joueur clique sur 'Lancer la partie'"""
    if len(game.players) < 2:
        sio.emit('notification', {'message': "Il faut au moins 2 joueurs !"}, to=sid)
        return

    print("Lancement de la partie !")
    game.start_game()
    
    # On prévient tout le monde que ça commence
    sio.emit('game_started', {})
    broadcast_game_state()

@sio.on('play_cards')
@sio.on('play_cards')
def handle_play(sid, data):
    player = sid_to_player.get(sid)
    if not player: return

    try:
        p_index = game.players.index(player)
    except ValueError: return

    cards_codes = data.get('cards', [])
    cards_obj = []
    
    if not cards_codes:
        success, msg = game.play_move(p_index, [])
    else:
        for code in cards_codes:
            rank = code[:-1]
            suit = code[-1]
            cards_obj.append(Card(rank, suit))
        
        success, msg = game.play_move(p_index, cards_obj)

    if success:
        # Si le message contient "COUPE" ou "CARRÉ", on fait une notif spéciale
        if "COUPE" in msg or "CARRÉ" in msg:
            # CORRECTION ICI : On retire ", broadcast=True"
            # sio.emit sans 'to=' envoie automatiquement à tout le monde
            sio.emit('notification', {'message': f"⚡ {player.name} A COUPÉ LE PLI ! ⚡"})
        else:
            print(f"{player.name} a joué : {cards_codes if cards_codes else 'PASSE'}")
            
        broadcast_game_state()
    else:
        # Ici on garde 'to=sid' car c'est une erreur pour un seul joueur
        sio.emit('notification', {'message': f"Erreur: {msg}"}, to=sid)

if __name__ == '__main__':
    eventlet.wsgi.server(eventlet.listen(('', 5000)), app)