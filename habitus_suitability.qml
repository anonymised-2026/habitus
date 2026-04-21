<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="AllStyleCategories">
  <pipe>
    <rasterrenderer band="1" classificationMin="0" classificationMax="1"
                    type="singlebandpseudocolor" opacity="1">
      <rastershader>
        <colorrampshader clip="0" colorRampType="INTERPOLATED"
                         classificationMode="2" minimumValue="0" maximumValue="1">
          <item color="#eaedf0" alpha="255" value="0"     label="0.000  Unsuitable"/>
          <item color="#c9d5de" alpha="255" value="0.125" label="0.125"/>
          <item color="#a0bece" alpha="255" value="0.25"  label="0.250  Low"/>
          <item color="#72a5b8" alpha="255" value="0.375" label="0.375"/>
          <item color="#4490a0" alpha="255" value="0.5"   label="0.500  Moderate"/>
          <item color="#237a82" alpha="255" value="0.625" label="0.625"/>
          <item color="#136860" alpha="255" value="0.75"  label="0.750  High"/>
          <item color="#006837" alpha="255" value="0.875" label="0.875"/>
          <item color="#1a9641" alpha="255" value="1"     label="1.000  Optimal"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
    <huesaturation grayscaleMode="0" saturation="0" colorizeOn="0"/>
    <rasterresampling maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
