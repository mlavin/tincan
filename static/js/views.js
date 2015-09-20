(function ($, Backbone, _, app) {
    'use strict';

    var errorTemplate = _.template($('#error-message-template').html()),

    SingleFileView = Backbone.View.extend({
        tagName: 'div',
        className: 'transfer',
        initialize: function (options) {
            this.file = options.file;
            this.file.on('change', $.proxy(this.render, this));
            this.file.on('remove', $.proxy(this.remove, this));
            this.template = _.template($(options.templateName).html());
        },
        render: function () {
            this.$el.html(this.template(this.file.toJSON()));
        }
    }),

    BaseFileView = Backbone.View.extend({
        el: '#files',
        initialize: function (options) {
            this.room = options.room;
            this.channel = this.room.getChannel();
            this.channel.onopen = $.proxy(this.connected, this);
            this.channel.onmessage = $.proxy(this.channelMessage, this);
            this.channel.onFileProgress = $.proxy(this.progress, this);
            this.template = _.template($(this.templateName).html());
            this.files = new Backbone.Collection();
            this.files.on('add', $.proxy(this.addFile, this));
            this.files.on('remove', $.proxy(this.removeFile, this));
        },
        render: function () {
            this.$el.html(this.template({}));
        },
        connected: function (userid) {
            console.debug('Connected with ', userid);
        },
        channelMessage: function (message, userid, latency) {
            if (message.type && message.file) {
                this.trigger('file:' + message.type, message.file, userid, latency);
            }
        },
        addFile: function (file) {
            var view = new SingleFileView({
                file: file,
                templateName: this.fileTemplate
            });
            this.$el.prepend(view.$el);
            view.render();
        },
        removeFile: function (file) {
            console.debug('File removed ', file);
        },
        progress: function (chunk) {
            var local = this.files.find(function (f) {
                var inner = f.get('file');
                return inner && inner.uuid && inner.uuid === chunk.uuid;
            });
            if (local) {
                local.set({progress: chunk});
                this.trigger('file:progress', local, chunk);
            }
        }
    }),

    SendFilesView = BaseFileView.extend({
        templateName: '#upload-template',
        fileTemplate: '#upload-file-template',
        events: {
            'dragover .upload': 'over',
            'dragend .upload': 'leave',
            'drop .upload': 'drop'
        },
        initialize: function (options) {
            BaseFileView.prototype.initialize.apply(this, arguments);
            // Create new channel
            this.channel.open(this.room.get('room'));
            // Bind expected channel events
            this.on('file:accept', function (file) {
                var local = this.files.get(file);
                this.channel.send(local.get('file'));
            }, this);
            this.on('file:progress', function (file, chunk) {
                if (chunk.sent === 1) {
                    this.channel.send({type: 'start', file: file});
                }
            }, this);
        },
        over: function (e) {
            e.preventDefault();
            $(e.target).addClass('hover');
            return false;
        },
        leave: function (e) {
            e.preventDefault();
            $(e.target).removeClass('hover');
            return false;
        },
        drop: function (e) {
            e.preventDefault();
            $(e.target).removeClass('hover');
            _.each(e.originalEvent.dataTransfer.files, this.queueFile, this);
        },
        queueFile: function (file) {
            this.files.add({
                id: crypto.getRandomValues(new Uint32Array(1))[0],
                file: file,
                name: file.name,
                type: file.type,
                size: file.size,
                accepted: false,
                url: '',
                progress: {}
            });
        },
        connected: function (userid) {
            // Send user info about current files
            this.files.each(function (f) {
                this.channel.send({type: 'offer', file: f});
            }, this);
        }
    }),

    AcceptFilesView = BaseFileView.extend({
        templateName: '#receiver-template',
        fileTemplate: '#recieve-file-template',
        events: {
            'click .accept': 'accept',
            'dragend .upload': 'leave',
            'drop .upload': 'drop'
        },
        initialize: function (options) {
            BaseFileView.prototype.initialize.apply(this, arguments);
            // Join channel
            this.channel.connect(this.room.get('room'));
            this.channel.onFileReceived = $.proxy(this.fileReceived, this);
            // Bind expected channel events
            this.on('file:offer', function (file) {
                this.files.add(file);
            }, this);
            this.on('file:start', function (file) {
                var local = this.files.get(file.id),
                    inner = local.get('file');
                inner.uuid = file.file.uuid;
                local.set({file: inner, progress: file.progress});
            }, this);
        },
        accept: function (e) {
            e.preventDefault();
            var id = $(e.target).data('id'),
                file = this.files.get(id);
            this.channel.send({type: 'accept', file: file});
            file.set({accepted: true});
        },
        fileReceived: function (file) {
            var local = this.files.findWhere({name: file.name});
            local.set({url: file.url});
        },
        connected: function (userid) {
            $('.loading', this.$el).fadeOut();
        }
    });

    app.HomepageView = Backbone.View.extend({
        el: '#home',
        events: {
            'click .button': 'newRoom'
        },
        render: function () {
            this.$el.show();
        },
        hide: function () {
            this.$el.hide();
        },
        newRoom: function (e) {
            e.preventDefault();
            $('.error', this.$el).remove();
            app.rooms.create({}, {
                success: function (model, response, options) {
                    window.location.hash = '#room/' + model.get('room');
                },
                error: function (model, response, options) {
                    console.debug('Error creating a room: ', response);
                    $(e.target).before(
                        errorTemplate({message: 'Unable to create a room. Please try again later.'})
                    );
                }
            });
        }
    });

    app.RoomView = Backbone.View.extend({
        el: '#room',
        initialize: function (options) {
            var self = this;
            this.room = app.rooms.get(options.room);
            if (this.room) {
                // Room already in the collection.
                // This is the room creator.
                this.files = new SendFilesView({room: this.room});
                this.files.render();
            } else {
                // Room not in the collection.
                // Peer has joined the room.
                this.room = app.rooms.push({room: options.room});
                this.room.fetch({
                    success: function (model, response, options) {
                        self.files = new AcceptFilesView({room: self.room});
                        self.files.render();
                    },
                    error: function (model, response, options) {
                        console.debug('Error joining a room');
                        console.debug(response);
                    }
                });
            }
        },
        render: function () {
            this.$el.show();
        }
    });

})(jQuery, Backbone, _, app);
