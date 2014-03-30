var views = (function ($, _, Backbone) {
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
        initialize: function (options) {
            this.options = options;
            this.server = this.options.server;
            this.server.on('new-peer', function () {
                console.log('Peer Connected!');
            });
        },
        render: function () {
            $('.page').removeClass('active');
            this.$el.addClass('active');
        }
    }),
    PeerView = Backbone.View.extend({
        el: '#room',
        initialize: function (options) {
            this.options = options;
            this.server = this.options.server;
            this.room = this.options.room;
        },
        render: function () {
            this.server.joinRoom(this.room)
                .then(_.bind(this.validRoom, this))
                .fail(_.bind(this.invalidRoom, this));
            $('.page').removeClass('active');
            this.$el.addClass('active');
        },
        validRoom: function () {

        },
        invalidRoom: function () {

        }
    });
    return {
        homepage: HomePageView,
        leader: LeaderView,
        peer: PeerView,
    }
})(jQuery, _, Backbone);