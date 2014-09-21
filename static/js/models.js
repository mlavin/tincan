(function ($, Backbone, _, app, DataChannel) {

    var Socket = function (server) {
        this.server = server;
        this.ws = null;
        this.connected = new $.Deferred();
        this.open();
    };

    Socket.prototype = _.extend(Socket.prototype, Backbone.Events, {
        open: function () {
            if (this.ws === null) {
                this.ws = new WebSocket(this.server);
                this.ws.onopen = $.proxy(this.onopen, this);
                this.ws.onmessage = $.proxy(this.onmessage, this);
                this.ws.onclose = $.proxy(this.onclose, this);
                this.ws.onerror = $.proxy(this.onerror, this);
            }
            return this.connected;
        },
        close: function () {
            if (this.ws && this.ws.close) {
                this.ws.close();
            }
            this.ws = null;
            this.connected = new $.Deferred();
            this.trigger('closed');
        },
        onopen: function () {
            this.connected.resolve(true);
            this.trigger('open');
        },
        onmessage: function (message) {
            var result = JSON.parse(message.data);
            this.trigger('message', result, message);
        },
        onclose: function (e) {
            var next = null,
                step = 0,
                count = 0,
                callback;
            console.debug('Websocket connection closed. ', e.reason);
            this.close();
            if (4200 <= e.code && e.code < 4299) {
                // Fast reconnect with slow backoff
                next = 100;
                step = 10;
            } else if (4100 <= e.code && e.code < 4199) {
                // Reconnect after a few seconds and backoff quickly
                next = 2000;
                step = 1000;
            }
            if (next !== null) {
                this.on('open', function () {
                    next = null;
                    this.off('open');
                    this.off('error');
                }, this);
                callback = $.proxy(function () {
                    count = count + 1;
                    next = next + step * count;
                    if (count < 1000) {
                        console.debug('Connect retry number ', count);
                        this.open();
                    } else {
                        next = null;
                        console.debug('Giving up on reconnection after ', count, ' attempts.');
                    }
                }, this);
                this.on('error', function () {
                    setTimeout(callback, next);
                }, this);
                setTimeout(callback, next);
            } else {
                this.off('open');
                this.off('error');
            }
        },
        onerror: function (error) {
            this.trigger('error', error);
            this.close();
        },
        send: function (message) {
            var self = this,
                payload = JSON.stringify(message);
            this.connected.done(function () {
                self.ws.send(payload);
            });
        }
    });

    var Room = Backbone.Model.extend({
        idAttribute: 'room',
        getChannel: function () {
            var self = this,
                channel = new DataChannel();
            channel.openSignalingChannel = function (config) {
                var socket = new Socket(self.get('socket'));
                if (config.onopen) setTimeout(config.onopen, 1000);
                socket.on('message', function (message, raw) {
                    config.onmessage(message);
                });
                socket.channel = config.channel || this.channel;
                return socket;
            };
            channel.autoCloseEntireSession = true;
            channel.autoSaveToDisk = false;
            return channel;
        }
    }),
    
    Rooms = Backbone.Collection.extend({
        model: Room,
        url: app.roomsURL
    });

    app.rooms = new Rooms();

})(jQuery, Backbone, _, app, DataChannel);
