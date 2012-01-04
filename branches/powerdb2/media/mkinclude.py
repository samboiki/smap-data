
import sys

print """
    <link rel="stylesheet" type="text/css" href="/media/smap/css/anytimec.css"/>                                                                
    <link rel="stylesheet" type="text/css" href="/media/jquery-ui/css/smoothness/jquery-ui-1.8.16.custom.css"/>                                 
    <link rel="stylesheet" type="text/css" href="/media/smap/css/plot.css"/>                                                                    
"""

for f in sys.argv[1:]:
    print """    <script type="text/javascript" src="/media/%s"></script>""" % f

print """    
    <script type="text/javascript">                                                                                                             
  var _gaq = _gaq || [];                                                                                                                        
  _gaq.push(['_setAccount', 'UA-26137257-1']);                                                                                                  
  _gaq.push(['_trackPageview']);                                                                                                                
                                                                                                                                                
  (function() {                                                                                                                                 
    var ga = document.createElement('script'); ga.type = 'text/javascript';                                                                     
    ga.async = true;                                                                                                                            
    ga.src = ('https:' == document.location.protocol ? 'https://ssl' :                                                                          
    'http://www') + '.google-analytics.com/ga.js';                                                                                              
    var s = document.getElementsByTagName('script')[0];                                                                                         
    s.parentNode.insertBefore(ga, s);                                                                                                           
  })();                                                                                                                                         
    </script>                                                                                                                                   
"""
