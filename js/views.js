var views = (function ($, _, Backbone, getUserMedia, Offer) {
    var HomePageView = Backbone.View.extend({
        el: '#homepage',
        events: {
            'click #create-room': 'createRoom'
        },
        initialize: function (options) {
            this.options = options;
            this.server = this.options.server;
        },
        render: function () {
            $('.page').removeClass('active');
            this.$el.addClass('active');
        },
        createRoom: function (e) {
            e.preventDefault();
            this.server.createRoom().then(_.bind(this.enterRoom, this));
        },
        enterRoom: function (room) {
            window.location.hash = '#room/' + room;
        }
    }),
    LeaderView = Backbone.View.extend({
        el: '#room',
        template: '#leader-room',
        initialize: function (options) {
            this.options = options;
            this.server = this.options.server;
            this.server.on('new-peer', _.bind(this.onPeer, this));
            this.server.on('peer-msg', _.bind(this.onSignalMessage, this));
            this.template = _.template($(this.template).html());
        },
        render: function () {
            this.$el.html(this.template());
            $('.page').removeClass('active');
            this.$el.addClass('active');
        },
        onPeer: function () {
            $('#peer-status', this.$el).text('Connected').addClass('active');
            getUserMedia({audio:true, video:false, fake: true},
                _.bind(this.gotLocalStream, this), _.bind(this.reportFailure, this));
        },
        gotLocalStream: function (stream) {
            var self = this;
            this.offer = new Offer(this.server.room, stream);
            this.offer.on('local-offer', function (offerDesc) {
                self.server.send(JSON.stringify(offerDesc));
            });
        },
        reportFailure: function () {
            //
        },
        connectionOpen: function () {
            console.log('Connection open!');
        },
        onSignalMessage: function (msg) {
            if (this.offer && !this.answer) {
                // Assume the first message is the answer
                this.offer.acceptAnswer(JSON.parse(msg));
            }
        }
    }),
    PeerView = Backbone.View.extend({
        el: '#room',
        template: '#peer-room',
        initialize: function (options) {
            this.options = options;
            this.server = this.options.server;
            this.room = this.options.room;
            this.template = _.template($(this.template).html());
            this.server.on('peer-msg', _.bind(this.onSignalMessage, this));
        },
        render: function () {
            this.$el.html(this.template());
            this.server.joinRoom(this.room)
                .then(_.bind(this.validRoom, this))
                .fail(_.bind(this.invalidRoom, this));
            $('.page').removeClass('active');
            this.$el.addClass('active');
        },
        validRoom: function () {
            var self = this;
            getUserMedia({audio:true, video:false, fake: true},
                _.bind(this.gotLocalStream, this), _.bind(this.reportFailure, this));
        },
        invalidRoom: function () {

        },
        reportFailure: function () {

        },
        gotLocalStream: function (stream) {
            var self = this;
            self.offer = new Offer(this.server.room, stream);
            self.offer.on('local-answer', function (answerDesc) {
                console.log('answer');
                self.server.send(JSON.stringify(answerDesc));
            });
        },
        onSignalMessage: function (msg) {
            if (this.offer && !this.answer) {
                // Assume the first message is an offer
                this.offer.acceptOffer(JSON.parse(msg));
            }
        }
    });
    return {
        homepage: HomePageView,
        leader: LeaderView,
        peer: PeerView,
    }
})(jQuery, _, Backbone, getUserMedia, Offer);