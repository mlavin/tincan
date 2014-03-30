var SignalConnection = (function ($, _, Backbone) {
    function SignalConnection(url) {
        this.url = url;
        this.events = _.extend({}, Backbone.Events);
        this.room = null;
        this.connected = new $.Deferred();
    }

    SignalConnection.prototype.on = function (event, callback, context) {
        this.events.on(event, callback, context);
    };

    SignalConnection.prototype.trigger = function (event, args) {
        this.events.trigger(event, args);
    };

    SignalConnection.prototype.connect = function () {
        if (!this.ws) {
            this.ws = new WebSocket(this.url);
            this.ws.onopen = _.bind(this.onopen, this);
            this.ws.onmessage = _.bind(this.onmessage, this);
        }
        return this.connected
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
        console.log(msg);
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
            } else {
                this.trigger('peer-msg', [msg]);
            }
        }
    };

    SignalConnection.prototype.send = function (message) {
        var self = this;
        this.connect().then(function () {
            self.ws.send(message);
        });
    };

    SignalConnection.prototype.createRoom = function () {
        var self = this;
            result = new $.Deferred();
        this.connect().then(function () {
            self.send('CREATE');
            self.on('new-room', function (name) {
                self.room = name;
                result.resolve(name);
            });
        });
        return result;
    };

    SignalConnection.prototype.joinRoom = function (name) {
        var self = this;
            result = new $.Deferred();
        this.connect().then(function () {
            self.send('JOIN ' + name);
            self.on('joined-room', function (name) {
                self.room = name;
                result.resolve(name);
            });
            self.on('invalid-room', function (error) {
                result.reject(name);
            });
        });
        return result;
    };

    return SignalConnection;
})(jQuery, _, Backbone);
