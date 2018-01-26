var mapnik = require('tilestrata-mapnik');
var mapnikNative = require('mapnik');
var SphericalMercator = require('@mapbox/sphericalmercator');
var async = require("async");
var fs = require('fs');

var renderers = {};

var sm = new SphericalMercator({ size: 256 });

//TODO: Clean initialized renderes by timestamp of last usage

function find_renderers(server, bbox, callback) {
  var infos = [];
  for (var key in renderers) {
    if (!renderers.hasOwnProperty(key)) {
      continue;
    }

    var r = renderers[key];

    if (r.bbox[0] > bbox[2] || r.bbox[2] < bbox[0] || r.bbox[1] > bbox[3] || r.bbox[3] < bbox[1]) {
      continue;
    }

    infos.push(key);
  }

  async.map(infos, function (key, cb) {
    info = renderers[key];
    if (info.renderer) {
      return cb(null, info.renderer);
    }

    var renderer = mapnik({
        pathname: 'mapnik-config/' + info.mapnik_config,
        tileSize: 256,
        scale: 1
    });

    renderer.init(server, function(err) {
      if (err) {
        cb(err);
      }
//TODO Remember tile and continue when initialization was finished
      renderers[info.mapnik_config].renderer = renderer;

      console.log("Renderer for " + info.mapnik_config + " initialized")
      cb(null, info.renderer);
    });
  }, callback);
}

function init_renderers(server, callback) {
  fs.readdir('mapnik-config', function(err, files) {
    for (var i = 0; i < files.length; i++) {
      var g = files[i].match(/N(\d{2})E(\d{3}).xml/);
      if (!g) {
        continue;
      }

      var lat = parseInt(g[1]), lon = parseInt(g[2]);

      var bbox = [lon, lat, lon + 1, lat + 1], mapnik_config = g[0];

      renderers[mapnik_config] = {bbox: bbox, mapnik_config: mapnik_config};
    }
    console.log("Renderers initialized")
    callback(null);
  });
}


function serve(server, bbox, tile, callback) {
  find_renderers(server, bbox, function(err, renderers) {
    if (err) {
      callback(err);
    }

    if (renderers.length == 0) {
      return callback("renderers not found for bbox " + bbox);
    }

    render_tile(tile, renderers, callback);
  });
}

function merge_images(images, callback) {
  var intermediate = new mapnikNative.Image(256, 256);
  intermediate.premultiply(function (err, intermediate) {
    if (err) {
      return callback(err);
    }

    async.reduce(images, intermediate, function(memo, image, cb) {
      memo.composite(image, function(err, image) {
        cb(null, image);
      });
    }, function(err, memo) {
      if (err) {
        return callback(err);
      }

      memo.demultiply(callback);
    });
  });
}

function render_tile(tile, renderers, callback) {
  async.map(renderers, function(renderer, callback) {
    renderer.serve(null, tile, function(err, buffer, headers) {
      mapnikNative.Image.fromBytes(buffer, function(err, image) {
        image.premultiply(function (err) {
          callback(err, image);
        });
      });
    })
  }, function(err, images) {
    if (err) {
      return callback(err);
    }

    merge_images(images, function (err, image) {
      if (err) {
        return callback(err);
      }

      image.encode('png', function(err, buffer) {
        if (err) {
          return callback(err);
        }

        callback(null, buffer, {'Content-Type': 'image/png'});
      });
    });
  });
}

module.exports = function() {
  return {
    name: 'multimapnik',
    init: function(server, callback) {
      init_renderers(server, callback);
    },

    serve: function(server, tile, callback) {
      var bbox = sm.bbox(tile.x, tile.y, tile.z);

      serve(server, bbox, tile, callback);
    },
    destroy: function(server, callback) {
      //TODO: Destroy renderers
      callback(null);
    }
  }
}
