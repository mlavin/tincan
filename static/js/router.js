(function ($, Backbone, _, app) {
    var AppRouter = Backbone.Router.extend({
        routes: {
            '': 'home',
            'room/:id': 'joinRoom'
        },
        initialize: function (options) {
            this.home = new app.HomepageView();
            Backbone.history.start();
        },
        home: function () {
            this.home.render();
        },
        joinRoom: function (id) {
            var view = new app.RoomView({room: id});
            this.home.hide();
            view.render();
        }
    });

  app.router = AppRouter;

})(jQuery, Backbone, _, app);