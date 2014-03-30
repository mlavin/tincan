(function ($) {
    function SignalConnection(server) {
        this.ws = new WebSocket(server);
        this.events = _.extend({}, Backbone.Events);
        this.room = null;
        this.connected = new $.Deferred();
        this.ws.onopen = _.bind(this.onopen, this);
        this.ws.onmessage = _.bind(this.onmessage, this);
    }

    SignalConnection.prototype.on = function (event, callback, context) {
        this.events.on(event, callback, context);
    };

    SignalConnection.prototype.trigger = function (event, args) {
        this.events.trigger(event, args);
    };

    SignalConnection.prototype.onopen = function () {
        this.connected.resolve(true);
    };

    function _isRoomMessage(msg) {
        var createdRE = /CREATED\s(\d+)/,
            joinedRE = /JOINED\s(\d+)/,
            invalidRE = /INVALID ROOM\s(\d+)/,
            result = createdRE.exec(msg),
            room = created = error = null;
            if (result) {
                room = result[1];
                created = true;
            } else {
                result = joinedRE.exec(msg);
                if (result) {
                    room = result[1];
                    created = false;
                }
            }
            if (room === null) {
                result = invalidRE.exec(msg);
                if (result) {
                    error = msg;
                }
            }
        return {room: room, created: created, error: error};
    }

    function _isConnectedPeer(msg) {
        var peerRE = /PEER CONNECTED/;
        if (peerRE.exec(msg)) {
            return true;
        }
        return false;
    }

    SignalConnection.prototype.onmessage = function (message) {
        var msg = message.data,
            roomMsg;
        if (this.room === null) {
            roomMsg = _isRoomMessage(msg);
            if (roomMsg.room) {
                if (roomMsg.created) {
                    this.trigger('new-room', [roomMsg.room]);
                } else {
                    this.trigger('joined-room', [roomMsg.room]);
                }
            } else if (roomMsg.error) {
                this.trigger('invalid-room', [roomMsg.error]);
            }
        } else {
            if (_isConnectedPeer(msg)) {
                this.trigger('new-peer');
            }
            console.log(msg);
        }
    };

    SignalConnection.prototype.send = function (message) {
        this.ws.send(message);
    };

    SignalConnection.prototype.createRoom = function () {
        var self = this;
            result = new $.Deferred();
        this.send('CREATE');
        this.on('new-room', function (name) {
            self.room = name;
            result.resolve(name);
        });
        return result;
    };

    SignalConnection.prototype.joinRoom = function (name) {
        var self = this;
            result = new $.Deferred();
        this.send('JOIN ' + name);
        this.on('joined-room', function (name) {
            self.room = name;
            result.resolve(name);
        });
        this.on('invalid-room', function (error) {
            result.reject(name);
        });
        return result;
    };

    var server = new SignalConnection('ws://localhost:8080/');

    $('#create-room').on('click', function (e) {
        e.preventDefault();
        server.createRoom().then(function (room) {
            window.location.hash = '#room/' + room;
        });
    });

    var AppRouter = Backbone.Router.extend({
        routes: {
            'room/:room': 'enterRoom' // #room/123
        },
        enterRoom: function (room) {
            console.log('Entered room');
            if (!server.room) {
                server.connected.then(function () {
                    server.joinRoom(room).then(function (name) {
                        console.log('Joined ' + name);
                    }).fail(function (error) {
                        alert(error);
                    });
                });
            } else {
                server.on('new-peer', function () {
                    alert('Peer Connected!');
                });
            }
        }
    });

    $(document).ready(function () {
        var router = new AppRouter();
        Backbone.history.start();
    });
})(jQuery);