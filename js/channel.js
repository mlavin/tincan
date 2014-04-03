var Channel = (function ($, _, Backbone, webrtcDetectedBrowser, getUserMedia,
    RTCPeerConnection, RTCSessionDescription, RTCIceCandidate) {
    var isChrome = webrtcDetectedBrowser === 'chrome',
        isFirefox = webrtcDetectedBrowser === 'firefox',
        servers = {"iceServers": [{"url": "stun:stun.l.google.com:19302"}]},
        connectionOptions = {},
        offerOptions = {
            optional: [],
            mandatory: {
                OfferToReceiveAudio: isFirefox,
                OfferToReceiveVideo: isFirefox
            }
        };

    function Channel(signal, leader) {
        var self = this;
        this.signal = signal;
        this.leader = leader;
        this.signal.on('peer-msg', _.bind(this.onSignalMessage, this));
        this.peer = new RTCPeerConnection(servers, connectionOptions);
        this.peer.onicecandidate = _.bind(this.onICECandiate, this);
        this.peer.ondatachannel = _.bind(this.onDataChannel, this);
        this.ready = new $.Deferred();
        this.events = _.extend({}, Backbone.Events);
        if (this.leader) {
            this.stream = new $.Deferred();
            if (isFirefox) {
                // Need to fetch media stream
                getUserMedia({audio: true, video: false, fake: true}, function (stream) {
                    self.peer.addStream(stream);
                    self.stream.resolve(true);
                }, _.bind(this.onError, this));
            } else {
                this.stream.resolve(true);
                this.channel = this.peer.createDataChannel(this.signal.room);
                this.onDataChannel({channel: this.channel});
            }
            this.stream.done(function () {
                self.peer.createOffer(
                    _.bind(self.onlocalDescription, self),
                    _.bind(self.onError, self),
                    offerOptions
                );
            });
        }        
    }

    Channel.prototype.on = function (event, callback, context) {
        this.events.on(event, callback, context);
    };

    Channel.prototype.trigger = function (event, args) {
        this.events.trigger(event, args);
    };

    Channel.prototype.onError = function (e) {
        console.log('Caught Error');
        console.log(e);
        this.ready.reject(e);
    };

    Channel.prototype.onSignalMessage = function (msg) {
        var data = JSON.parse(msg),
            self = this;
        if (data.sdp) {
            this.peer.setRemoteDescription(new RTCSessionDescription(data.sdp), function () {
                if (self.peer.remoteDescription.type === 'offer') {
                    self.peer.createAnswer(
                        _.bind(self.onlocalDescription, self),
                        _.bind(self.onError, this),
                        offerOptions
                    );
                }
            }, _.bind(this.onError, this));
        } else if (data.candidate) {
            this.peer.addIceCandidate(new RTCIceCandidate(data.candidate));
        }
    };

    Channel.prototype.onlocalDescription = function (desc) {
        var self = this;
        this.peer.setLocalDescription(desc, function () {
            var message = JSON.stringify({'sdp': self.peer.localDescription});
            self.signal.send(message);
        }, _.bind(this.onError, this));
    };

    Channel.prototype.onICECandiate = function (e) {
        var message = JSON.stringify({'candidate': e.candidate});
        if (e.candidate) {
            this.signal.send(message);
        }
    };

    Channel.prototype.onDataChannel = function (e) {
        this.channel = e.channel;
        this.channel.onmessage = _.bind(this.onChannelMessage, this);
        this.channel.onopen = _.bind(this.onChannelOpen, this);
        this.channel.onerror = _.bind(this.onError, this);
    };

    Channel.prototype.onChannelOpen = function () {
        this.ready.resolve(this.channel);
    };

    Channel.prototype.onChannelMessage = function (message) {
        this.trigger('message', message);
    };

    Channel.prototype.send = function (message) {
        this.ready.then(function (channel) {
            channel.send(message);
        });
    };

    return Channel;
})($, _, Backbone, webrtcDetectedBrowser, getUserMedia,
    RTCPeerConnection, RTCSessionDescription, RTCIceCandidate);