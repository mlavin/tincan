(function ($, Backbone, _, app, DataChannel) {

    var Socket = function (server, token, channel) {
        this.server = server;
        this.token = token;
        this.channel = channel;
        this.ws = null;
        this.connected = new $.Deferred();
        this.open();
    };

    Socket.prototype = _.extend(Socket.prototype, Backbone.Events, {
        open: function () {
            if (this.ws === null) {
                this.ws = new WebSocket(this.url());
                this.ws.onopen = $.proxy(this.onopen, this);
                this.ws.onmessage = $.proxy(this.onmessage, this);
                this.ws.onclose = $.proxy(this.onclose, this);
                this.ws.onerror = $.proxy(this.onerror, this);
            }
            return this.connected;
        },
        url: function () {
            return this.server + '?' + $.param({token: this.token, channel: this.channel});
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
            console.debug('Websocket connection closed. ', e.reason);
            this.close();
            if (4200 <= e.code && e.code < 4299) {
                // Fast reconnect with slow backoff
                this.reconnect(100, 10, 1);
            } else if (4100 <= e.code && e.code < 4199) {
                // Reconnect after a few seconds and backoff quickly
                this.reconnect(2000, 1000, 1);
            } else if (4000 <= e.code && e.code < 4099) {
                // URL needs to be refreshed
                this.refresh();
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
        },
        reconnect: function (next, step, count) {
            if (count < 1000) {
                console.debug('Connect retry number ', count);
                this.once('error', function () {
                    this.reconnect(next + step * count, step, count + 1);
                }, this);
                this.once('open', function () {
                    this.off('error');
                }, this);
                setTimeout($.proxy(this.open, this), next);
            } else {
                console.debug('Giving up on reconnection after ', count, ' attempts.');
            }
        },
        refresh: function (token) {
            if (typeof(token) !== 'undefined') {
                console.debug('Resetting socket token.');
                this.token = token;
                this.open();
            } else if (this.token !== null) {
                console.debug('Token refresh required.');
                this.token = null;
                this.trigger('refresh');
            }
        }
    });

    var Room = Backbone.Model.extend({
        idAttribute: 'room',
        getChannel: function () {
            var self = this,
                channel = new DataChannel();
            channel.userid = this.get('user');
            channel.openSignalingChannel = function (config) {
                console.debug('Open new signalling channel ', config);
                var socketChannel = config.channel || this.channel,
                    socket = new Socket(self.get('socket'), self.get('token'), socketChannel);

                socket.on('refresh', function () {
                    console.debug('Refreshing socket token.');
                    // Refetch the room state
                    self.fetch({success: function (model) {
                        socket.refresh(model.get('token'));
                    }});
                });

                if (config.onopen) {
                    setTimeout(config.onopen, 1000);
                }
                
                socket.on('message', function (message, raw) {
                    config.onmessage(message);
                });
                
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
