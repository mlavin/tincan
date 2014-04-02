var views = (function ($, _, Backbone, getUserMedia, Channel) {
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
            this.template = _.template($(this.template).html());
        },
        render: function () {
            this.$el.html(this.template({room: this.server.room}));
            $('.page').removeClass('active');
            this.$el.addClass('active');
        },
        onPeer: function () {
            var self = this;
            $('#peer-status', this.$el).text('Connected').addClass('active');
            this.channel = new Channel(this.server, true);
            this.channel.on('message', function (message) {
                console.log(message.data);
            });
            this.channel.ready.done(function () {
                self.channel.send('Ping');
            }).fail(function () {
                console.log('Connection failed.');
            });
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
            this.channel = new Channel(this.server, false);
            this.channel.on('message', function (message) {
                console.log(message.data);
                self.channel.send('Pong');
            });
        },
        invalidRoom: function () {

        }
    });
    return {
        homepage: HomePageView,
        leader: LeaderView,
        peer: PeerView,
    }
})(jQuery, _, Backbone, getUserMedia, Channel);