var Offer = (function (_, Backbone, attachMediaStream, RTCPeerConnection, RTCSessionDescription, RTCIceCandidate) {
    var servers = {"iceServers": [{"url": "stun:stun.l.google.com:19302"}]},
        connectionOptions = {optional: [{RtpDataChannels: true}]},
        noop = function () {};

    function Offer(name, stream) {
        var self = this;
        this.name = name;
        this.stream = stream;
        this.sender = new RTCPeerConnection(servers, connectionOptions);
        this.receiver = new RTCPeerConnection(servers, connectionOptions);
        this.sender.addStream(this.stream);
        this.channel = this.sender.createDataChannel(this.name, {reliable:false});
        this.sender.onconnection = function (e) {
            self.trigger('channel-connection', [self.channel]);
        };
        this.sender.createOffer(function (e) {
            self.sender.setLocalDescription(e);
            self.trigger('local-offer', [e]);
        }, noop);
        this.events = _.extend({}, Backbone.Events);
    }

    Offer.prototype.on = function (event, callback, context) {
        this.events.on(event, callback, context);
    };

    Offer.prototype.trigger = function (event, args) {
        this.events.trigger(event, args);
    };

    Offer.prototype.acceptOffer = function (offer) {
        var self = this;
        this.receiver.onaddstream = function (e) {
            var el = new Audio();
            el.autoplay = true;
            attachMediaStream(el, e.stream);
        };

        this.receiver.ondatachannel = function (e) {
            self.channel = e.channel || e;
        }

        this.receiver.setRemoteDescription(new RTCSessionDescription(offer));

        this.receiver.onicecandidate = function (e) {
            if (self.sender && e.candidate) {
                self.sender.addIceCandidate(new RTCIceCandidate(e.candidate));
            }
        };

        this.receiver.createAnswer(function (e) {
            self.receiver.setLocalDescription(e);
            self.trigger('local-answer', [e]);
        }, noop);
    };

    Offer.prototype.acceptAnswer = function (answer) {
        var self = this;
        this.sender.setRemoteDescription(new RTCSessionDescription(answer));

        this.sender.onicecandidate = function (e) {
            if (self.receiver && e.candidate) {
                self.receiver.addIceCandidate(new RTCIceCandidate(e.candidate));
            }
        };
    };

    return Offer;
})(_, Backbone, attachMediaStream, RTCPeerConnection, RTCSessionDescription, RTCIceCandidate);