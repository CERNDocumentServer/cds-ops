jQuery(function($){
    var jcrop_api
      , current;

    $('body').on('click', '[rel=crop]', function(){

        var $this = $(this);

        current = {
            original : $this.data('original'),
            thumb    : $this.data('thumb'),
            width    : $this.data('width'),
            height   : $this.data('height'),
            parent   : $this,
            crop     : ($this.data('crop') !== undefined) ? $this.data('crop') : null,
            isCropped: ($this.data('cropped') == 1) ? true : false,
            id       : $this.data('id'),
            name     : $this.data('name')
        };

        // Fire up event crop.click
        $('body').trigger('crop.click', [$this, current]);

        $.magnificPopup.open({
            modal: true,
            key: 'crop-popup',
            midClick: true,
            type: 'inline',
            closeBtnInside: true,
            items:{
                src: '<div class="white-popup-big">'+
                     '<img src="/img/ajax-loader.gif" id="target" class="empty-state" />'+
                     '<div class="button-wrapper crop-tool-links">'+
                     '<a href="javascript:void(0)" rel="close">Cancel</a>'+
                     '<a href="javascript:void(0)" style="display:none" rel="save">Save</a>'+
                     '</div>'+
                     '</div>',
                type: 'inline'
            },
            callbacks: {
                open: function(){
                    // What to do when it opens
                    $('body').trigger('crop.open', [this, current]);
                },
                afterClose: function(){
                    // What to do when it closes
                    $('body').trigger('crop.close', [this, current]);
                    jcropDestroy();
                }
            }
        });
    });

    $('body').on('click', '[rel=save]', saveCrop);
    $('body').on('click', '[rel=close]', closeCrop);

    $('body').on('overlay.ready', function(event, current, response, dimensions){
        $('<img />',{
            id : 'target',
            src: response
        }).load(function(){
            $('#target').replaceWith($(this));
            $('[rel=save]').show();
            setTimeout(function(){
                // Calculate the real dimensions ratio
                jcropInit(current.width, current.height, current, dimensions);
            }, 0)
        })
    });
    function jcropCoords(c){
        current.crop = c;
    }
    function jcropInit(x, y, current, dimensions){
        $('body').trigger('crop.beforeInit');
        // Check if has allready init
        var animate = (!current.isCropped || current.crop.x === undefined)
                       ? [100, 100, 400, 300]:
                                         [current.crop.x,
                                          current.crop.y,
                                          current.crop.x2,
                                          current.crop.y2];

        x = (x !== undefined) ? x : $('#target').width();
        y = (y !== undefined) ? y : $('#target').height();
        dimensions = JSON.parse(dimensions);
        // Init Crop
        $('#target').Jcrop({
          onSelect:    jcropCoords,
          aspectRatio: 4/3,
          bgColor:     '#ffffff',
          bgOpacity:   0.5,
          minSize: [ 80, 80 ],
          trueSize: [parseInt(dimensions.x), parseInt(dimensions.y)],
          allowSelect: false
        },function(){
            $('body').trigger('crop.init', [this, current]);
            jcrop_api = this;
            jcrop_api.focus();
            jcrop_api.animateTo(animate);
        });
    }
    function jcropDestroy(){
        // Destroy Crop
        try{
            jcrop_api.destroy();
            current = null;
            return false;
        }catch(e){
            // Just make the expeption silent
            return false;
        }
    }
    function saveCrop(){
        $('body').trigger('crop.save', [this, current]);
        $('[rel=close]').hide();
        $(this).click(function () { return false; });
        $(this).text('Saving ...')
        current.parent.data('crop', current.crop);
        current.parent.data('cropped', 1);

        setTimeout(function(){
            $.magnificPopup.close();
        }, 500)

        $(this).prop('disabled', false);
    }
    function closeCrop(){
        $.magnificPopup.close();
    }
    function removeCrop(){
        //current.parent.data('cropped', 0);
        //current.parent.parent().find('.cropped').html();
    }
});
