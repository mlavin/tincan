var Channel = (function ($, _, Backbone, webrtcDetectedBrowser, getUserMedia, attachMediaStream,
    RTCPeerConnection, RTCSessionDescription, RTCIceCandidate) {
    var servers = {"iceServers": [{"url": "stun:stun.l.google.com:19302"}]},
        connectionOptions = {optional: [{RtpDataChannels: true}]},
        noop = function () {},
        logerror = function (err) {
            console.log(err);
        };

    function Channel(name) {
        var self = this;
        this.name = name;
        if (webrtcDetectedBrowser === 'firefox') {
            // Need to fetch media stream
            getUserMedia({audio:true, video:false, fake: true}, function (stream) {
                self.sender.addStream(stream);
            }, noop);
        }
        this.sender = new RTCPeerConnection(servers, connectionOptions);
        this.receiver = new RTCPeerConnection(servers, connectionOptions);
        this.channel = this.sender.createDataChannel(this.name, {reliable: false});
        this.channel.onmessage = _.bind(this.gotMessage, this);
        this.channel.onopen = function () {
            console.log('Channel Ready!');
        }
        this.channel.onerror = logerror;
        this.sender.onconnection = function (e) {
            console.log('Sender Data Channel');
            self.trigger('channel-connection', [self.channel]);
        };
        this.offer = new $.Deferred();
        this.ready = new $.Deferred();
        this.sender.createOffer(function (e) {
            self.sender.setLocalDescription(e, noop, logerror);
            self.receiver.setRemoteDescription(e, noop, logerror);
            self.offer.resolve(e);
            self.trigger('local-offer', [e]);
        }, noop);
        this.events = _.extend({}, Backbone.Events);
    }

    Channel.prototype.on = function (event, callback, context) {
        this.events.on(event, callback, context);
    };

    Channel.prototype.trigger = function (event, args) {
        this.events.trigger(event, args);
    };

    Channel.prototype.acceptOffer = function (offer) {
        var self = this;
        this.offer.then(function () {
            self.receiver.onaddstream = function (e) {
                var el = new Audio();
                el.autoplay = true;
                attachMediaStream(el, e.stream);
            };

            self.receiver.ondatachannel = function (e) {
                self.channel = e.channel || e;
                self.ready.resolve(self.channel);
                self.channel.onmessage = _.bind(self.gotMessage, self);
            }

            self.receiver.setRemoteDescription(new RTCSessionDescription(offer), noop, logerror);

            self.receiver.onicecandidate = function (e) {
                if (e.candidate) {
                    self.sender.addIceCandidate(new RTCIceCandidate(e.candidate));
                }
            };

            self.receiver.createAnswer(function (e) {
                self.receiver.setLocalDescription(e);
                self.trigger('local-answer', [e]);
            }, noop);
        });
    };

    Channel.prototype.acceptAnswer = function (answer) {
        var self = this;
        this.receiver.setLocalDescription(new RTCSessionDescription(answer), noop, logerror);
        this.sender.setRemoteDescription(new RTCSessionDescription(answer), noop, logerror);

        this.sender.onicecandidate = function (e) {
            if (e.candidate) {
                self.receiver.addIceCandidate(new RTCIceCandidate(e.candidate));
            }
        };
        this.ready.resolve(this.channel);
    };

    Channel.prototype.send = function (message) {
        this.ready.then(function (channel) {
            channel.send(message);
        });
    };

    Channel.prototype.gotMessage = function (message) {
        console.log('Channel Message: ' +  message);
        this.trigger('message', [message]);
    };

    return Channel;
})($, _, Backbone, webrtcDetectedBrowser, getUserMedia, attachMediaStream,
    RTCPeerConnection, RTCSessionDescription, RTCIceCandidate);