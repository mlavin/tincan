(function ($, _, Backbone, views, SignalConnection) {
    var AppRouter = Backbone.Router.extend({
        initialize: function (options) {
            this.options = options;
            this.url = (this.options && this.options.url) || 'ws://localhost:8080/';
            this.server = new SignalConnection(this.url);
            this.homepage = new views.homepage({server: this.server});
        },
        routes: {
            '': 'homePage',
            'room/:room': 'enterRoom' // #room/123
        },
        homePage: function() {
            this.homepage.render();
        },
        enterRoom: function (room) {
            var view;
            if (!this.server.room) {
                view = new views.peer({server: this.server, room: room});
            } else {
                view = new views.leader({server: this.server});
            }
            view.render();
        }
    });

    $(document).ready(function () {
        var router = new AppRouter();
        Backbone.history.start();
    });
})(jQuery, _, Backbone, views, SignalConnection);