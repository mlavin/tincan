(function ($) {
    var server = new SignalConnection('ws://localhost:8080/');

    $('#create-room').on('click', function (e) {
        e.preventDefault();
        server.createRoom().then(function (room) {
            window.location.hash = '#room/' + room;
        });
    });

    var AppRouter = Backbone.Router.extend({
        routes: {
            'room/:room': 'enterRoom' // #room/123
        },
        enterRoom: function (room) {
            console.log('Entered room');
            if (!server.room) {
                server.connected.then(function () {
                    server.joinRoom(room).then(function (name) {
                        console.log('Joined ' + name);
                    }).fail(function (error) {
                        alert(error);
                    });
                });
            } else {
                server.on('new-peer', function () {
                    alert('Peer Connected!');
                });
            }
        }
    });

    $(document).ready(function () {
        var router = new AppRouter();
        Backbone.history.start();
    });
})(jQuery, Backbone, SignalConnection);