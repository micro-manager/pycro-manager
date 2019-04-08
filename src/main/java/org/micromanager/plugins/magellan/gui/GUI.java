///////////////////////////////////////////////////////////////////////////////
// AUTHOR:       Henry Pinkard, henry.pinkard@gmail.com
//
// COPYRIGHT:    University of California, San Francisco, 2015
//
// LICENSE:      This file is distributed under the BSD license.
//               License text is included with the source distribution.
//
//               This file is distributed in the hope that it will be useful,
//               but WITHOUT ANY WARRANTY; without even the implied warranty
//               of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
//
//               IN NO EVENT SHALL THE COPYRIGHT OWNER OR
//               CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
//               INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES.
//
package main.java.org.micromanager.plugins.magellan.gui;

import java.awt.Color;
import java.awt.Component;
import java.awt.Font;
import java.awt.event.FocusAdapter;
import java.awt.event.FocusEvent;
import java.io.File;
import java.util.prefs.Preferences;
import javax.swing.DefaultComboBoxModel;
import javax.swing.JFileChooser;
import javax.swing.JLabel;
import javax.swing.JRadioButton;
import javax.swing.JSpinner;
import javax.swing.JTable;
import javax.swing.event.DocumentEvent;
import javax.swing.event.DocumentListener;
import javax.swing.event.ListSelectionEvent;
import javax.swing.event.ListSelectionListener;
import javax.swing.table.AbstractTableModel;
import javax.swing.table.DefaultTableCellRenderer;
import javax.swing.table.TableCellRenderer;
import javax.swing.table.TableColumn;
import java.awt.FileDialog;
import java.awt.event.ComponentAdapter;
import java.awt.event.ComponentEvent;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;
import java.beans.PropertyChangeEvent;
import java.beans.PropertyChangeListener;
import java.io.IOException;
import java.util.LinkedList;
import javax.swing.DefaultCellEditor;
import javax.swing.JSplitPane;
import javax.swing.JTextField;
import javax.swing.SwingConstants;
import javax.swing.SwingUtilities;
import main.java.org.micromanager.plugins.magellan.acq.AcqDurationEstimator;
import main.java.org.micromanager.plugins.magellan.acq.ExploreAcqSettings;
import main.java.org.micromanager.plugins.magellan.acq.FixedAreaAcquisitionSettings;
import main.java.org.micromanager.plugins.magellan.acq.MagellanEngine;
import main.java.org.micromanager.plugins.magellan.acq.MultipleAcquisitionManager;
import main.java.org.micromanager.plugins.magellan.acq.MultipleAcquisitionTableModel;
import main.java.org.micromanager.plugins.magellan.channels.ChannelComboBoxModel;
import main.java.org.micromanager.plugins.magellan.channels.ColorEditor;
import main.java.org.micromanager.plugins.magellan.channels.ColorRenderer;
import main.java.org.micromanager.plugins.magellan.channels.SimpleChannelTableModel;
import main.java.org.micromanager.plugins.magellan.coordinates.AffineGUI;
import main.java.org.micromanager.plugins.magellan.main.Magellan;
import main.java.org.micromanager.plugins.magellan.misc.ExactlyOneRowSelectionModel;
import main.java.org.micromanager.plugins.magellan.misc.GlobalSettings;
import main.java.org.micromanager.plugins.magellan.misc.JavaUtils;
import main.java.org.micromanager.plugins.magellan.misc.LoadedAcquisitionData;
import main.java.org.micromanager.plugins.magellan.misc.Log;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.RegionManager;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceManager;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceRegionComboBoxModel;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.XYFootprint;

/**
 *
 * @author Henry
 */
public class GUI extends javax.swing.JFrame {

   private static final String PREF_SIZE_WIDTH = "Magellan gui size width";
   private static final String PREF_SIZE_HEIGHT = "Magellan gui size height";
   private static final String PREF_SPLIT_PANE = "split pane location";
    private static final Color DARK_GREEN = new Color(0, 128, 0);
    private MagellanEngine eng_;
    private AcqDurationEstimator acqDurationEstimator_;
    private Preferences prefs_;
    private RegionManager regionManager_ = new RegionManager();
    private SurfaceManager surfaceManager_ = new SurfaceManager();
    private MultipleAcquisitionManager multiAcqManager_;
    private GlobalSettings settings_;
    private boolean storeAcqSettings_ = true;
    private int multiAcqSelectedIndex_ = 0;
    private LinkedList<JSpinner> offsetSpinners_ = new LinkedList<JSpinner>();
    private static GUI singleton_;

   public GUI(Preferences prefs, String version) {
      singleton_ = this;
      prefs_ = prefs;
      settings_ = new GlobalSettings(prefs_, this);
      this.setTitle("Micro-Magellan " + version);
      acqDurationEstimator_ = new AcqDurationEstimator();
      eng_ = new MagellanEngine(Magellan.getCore(), acqDurationEstimator_);
      multiAcqManager_ = new MultipleAcquisitionManager(this, eng_);
      initComponents();
      moreInitialization();
      this.setVisible(true);
      addGlobalSettingsListeners();
      storeCurrentAcqSettings();
      if (GlobalSettings.getInstance().firstMagellanOpening()) {
         new StartupHelpWindow();
      }      
   }
   
   public static GUI getInstance() {
      return singleton_;
   }
   
   public void acquisitionRunning(boolean running) {
      //disable or enabe the controls that cannot be changed during acquisition
      zStepSpinner_.setEnabled(!running);
      zStepLabel_.setEnabled(!running);
      acqTileOverlapLabel_.setEnabled(!running);
      acqOverlapPercentSpinner_.setEnabled(!running);
      tileOverlapPercentLabel_.setEnabled(!running);
      this.repaint();
   }
   
   public static void updateEstiamtedDurationLabel(final String text) {
      SwingUtilities.invokeLater(new Runnable() {
         @Override
         public void run() {
            singleton_.estDurationLabel_.setText(text);
         }
      });
   }

   public void acquisitionSettingsChanged() {
      //refresh GUI and store its state in current acq settings
      refreshAcqTabTitleText();
      storeCurrentAcqSettings();
   }

   public FixedAreaAcquisitionSettings getActiveAcquisitionSettings() {
      return multiAcqManager_.getAcquisitionSettings(multiAcqSelectedIndex_);
   }

   public XYFootprint getFootprintObject(int index) {
      //regions first then surfaces
      if (index < regionManager_.getNumberOfRegions()) {
         return regionManager_.getRegion(index);
      } else {
         return surfaceManager_.getSurface(index - regionManager_.getNumberOfRegions());
      }
   }

   public static SurfaceRegionComboBoxModel createSurfaceAndRegionComboBoxModel(boolean surfaces, boolean regions) {
      SurfaceRegionComboBoxModel model = new SurfaceRegionComboBoxModel(surfaces ? SurfaceManager.getInstance() : null,
              regions ? RegionManager.getInstance() : null);
      if (surfaces) {
         SurfaceManager.getInstance().addToModelList(model);
      }
      if (regions) {
         RegionManager.getInstance().addToModelList(model);
      }
      return model;
   }

    private void moreInitialization() {
       //add link to user guide label
       userGuideLink_.addMouseListener(new MouseAdapter() {
         @Override
         public void mousePressed(MouseEvent e) {
            new Thread(new Runnable() {
               @Override
               public void run() {
                  try {            
                     ij.plugin.BrowserLauncher.openURL("https://micro-manager.org/wiki/MicroMagellan");
                  } catch (IOException ex) {
                     Log.log("couldn't open User guide link");
                  }
               }
            }).start();
         }
      });
       //add link to citation
       citeLink_.addMouseListener(new MouseAdapter() {
         @Override
         public void mousePressed(MouseEvent e) {
            new Thread(new Runnable() {
               @Override
               public void run() {
                  try {            
                     ij.plugin.BrowserLauncher.openURL("http://www.nature.com/nmeth/journal/v13/n10/full/nmeth.3991.html");
                  } catch (IOException ex) {
                     Log.log("couldn't open citation link");
                  }
               }
            }).start();
         }
      });

        //exactly one acquisition selected at all times
        multipleAcqTable_.setSelectionModel(new ExactlyOneRowSelectionModel());
        multipleAcqTable_.getSelectionModel().addListSelectionListener(new ListSelectionListener() {
            @Override
            public void valueChanged(ListSelectionEvent e) {
                if (e.getValueIsAdjusting()) {
                    return;
                    //action occurs second time this method is called, after the table gains focus
                }
                multiAcqSelectedIndex_ = multipleAcqTable_.getSelectedRow();
                //if last acq in list is removed, update the selected index
                if (multiAcqSelectedIndex_ == multipleAcqTable_.getModel().getRowCount()) {
                    multipleAcqTable_.getSelectionModel().setSelectionInterval(multiAcqSelectedIndex_ - 1, multiAcqSelectedIndex_ - 1);
                }
                populateAcqControls(multiAcqManager_.getAcquisitionSettings(multiAcqSelectedIndex_));
            }
        });
        //Table column widths
        multipleAcqTable_.getColumnModel().getColumn(0).setMaxWidth(60); //order column
       channelsTable_.getColumnModel().getColumn(0).setMaxWidth(60); //Acitve checkbox column

       //set color renderer for channel table
       for (int col = 1; col < channelsTable_.getColumnModel().getColumnCount(); col++) {
          if (col == 4) {
             ColorRenderer cr = new ColorRenderer(true);
             ColorEditor ce = new ColorEditor((AbstractTableModel) channelsTable_.getModel(), col);
             channelsTable_.getColumnModel().getColumn(col).setCellRenderer(cr);
             channelsTable_.getColumnModel().getColumn(col).setCellEditor(ce);
          } else {
             DefaultTableCellRenderer renderer = new DefaultTableCellRenderer();
             renderer.setHorizontalAlignment(SwingConstants.LEFT); // left justify
             channelsTable_.getColumnModel().getColumn(col).setCellRenderer(renderer);
          }
          if (col == 2) {
              //left justified editor
              JTextField tf = new JTextField();
              tf.setHorizontalAlignment(SwingConstants.LEFT);
              DefaultCellEditor ed = new DefaultCellEditor(tf);
              channelsTable_.getColumnModel().getColumn(col).setCellEditor(ed);
          }
       }
      
        //load global settings     
        globalSavingDirTextField_.setText(settings_.getStoredSavingDirectory());
        //load explore settings
        exploreSavingNameTextField_.setText(ExploreAcqSettings.getNameFromPrefs());
        exploreZStepSpinner_.setValue(ExploreAcqSettings.getZStepFromPrefs());
        exploreTileOverlapSpinner_.setValue(ExploreAcqSettings.getExploreTileOverlapFromPrefs());

        populateAcqControls(multiAcqManager_.getAcquisitionSettings(0));
        enableAcquisitionComponentsAsNeeded();

        int width = settings_.getIntInPrefs(PREF_SIZE_WIDTH, Integer.MIN_VALUE);
        int height = settings_.getIntInPrefs(PREF_SIZE_HEIGHT, Integer.MIN_VALUE);
        if (height != Integer.MIN_VALUE && width != Integer.MIN_VALUE ) {
           this.setSize(width, height);
        } 
        
        //save resizing
        this.addComponentListener(new ComponentAdapter() {
           @Override
           public void componentResized(ComponentEvent e) {
              settings_.storeIntInPrefs(PREF_SIZE_WIDTH, GUI.this.getWidth());
              settings_.storeIntInPrefs(PREF_SIZE_HEIGHT, GUI.this.getHeight());
          }
       });
      

    }
    
    
    public void refreshAcquisitionSettings() {
        //so that acquisition names can be changed form multi acquisitiion table
        populateAcqControls(multiAcqManager_.getAcquisitionSettings(multiAcqSelectedIndex_));
    }

   private void refreshAcqTabTitleText() {
      JLabel l2 = new JLabel("Time");
      l2.setForeground(timePointsCheckBox_.isSelected() ? DARK_GREEN : Color.black);
      l2.setFont(acqTabbedPane_.getComponent(0).getFont().deriveFont(timePointsCheckBox_.isSelected() ? Font.BOLD : Font.PLAIN));
      acqTabbedPane_.setTabComponentAt(0, l2);
      JLabel l3 = new JLabel("Space");
      l3.setForeground(true ? DARK_GREEN : Color.black);
      l3.setFont(acqTabbedPane_.getComponent(1).getFont().deriveFont(true ? Font.BOLD : Font.PLAIN));
      acqTabbedPane_.setTabComponentAt(1, l3);
      JLabel l4 = new JLabel("Channels");
      l4.setForeground(((SimpleChannelTableModel) channelsTable_.getModel()).anyChannelsActive() ? DARK_GREEN : Color.black);
      l4.setFont(acqTabbedPane_.getComponent(2).getFont().deriveFont(((SimpleChannelTableModel) channelsTable_.getModel()).anyChannelsActive()
              ? Font.BOLD : Font.PLAIN));
      acqTabbedPane_.setTabComponentAt(2, l4);
      acqTabbedPane_.invalidate();
      acqTabbedPane_.validate();
   }

    private void enableAcquisitionComponentsAsNeeded() {
        //Set Tab titles
        refreshAcqTabTitleText();
        //Enable or disable time point stuff
        for (Component c : timePointsPanel_.getComponents()) {
            c.setEnabled(timePointsCheckBox_.isSelected());
        }
    }

    public void storeCurrentAcqSettings() {
        if (!storeAcqSettings_) {
            return;
        }
        FixedAreaAcquisitionSettings settings = multiAcqManager_.getAcquisitionSettings(multiAcqSelectedIndex_);
        //saving
        settings.dir_ = globalSavingDirTextField_.getText();
        settings.name_ = multiAcqManager_.getAcquisitionName(multiAcqSelectedIndex_);
        //time
        settings.timeEnabled_ = timePointsCheckBox_.isSelected();
        if (settings.timeEnabled_) {
            settings.numTimePoints_ = (Integer) numTimePointsSpinner_.getValue();
            settings.timePointInterval_ = (Double) timeIntervalSpinner_.getValue();
            settings.timeIntervalUnit_ = timeIntevalUnitCombo_.getSelectedIndex();
        }
        //space
        settings.tileOverlap_ = (Double) acqOverlapPercentSpinner_.getValue();
        if (acq2D3DTabbedPane_.getSelectedIndex() == 0) { //2D pane
            settings.spaceMode_ = FixedAreaAcquisitionSettings.REGION_2D;
            settings.footprint_ = getFootprintObject(footprint2DComboBox_.getSelectedIndex());
            if (useCollectionPlaneButton_.isSelected()) {
               settings.collectionPlane_ = surfaceManager_.getSurface(collectionPlaneCombo_.getSelectedIndex());
            } else {
                settings.collectionPlane_ = null;
            }
        } else if (acq2D3DTabbedPane_.getSelectedIndex() == 1) {
            settings.zStep_ = (Double) zStepSpinner_.getValue();
            settings.channelsAtEverySlice_ = acqOrderCombo_.getSelectedIndex() == 0;
            if (zStackTypeTabbedPane_.getSelectedIndex() == 0) {
                settings.spaceMode_ = FixedAreaAcquisitionSettings.SIMPLE_Z_STACK;
                settings.footprint_ = getFootprintObject(simpleZStackFootprintCombo_.getSelectedIndex());
                settings.zStart_ = (Double) zStartSpinner_.getValue();
                settings.zEnd_ = (Double) zEndSpinner_.getValue();
            } else if (zStackTypeTabbedPane_.getSelectedIndex() == 1) {
                settings.spaceMode_ = FixedAreaAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK;
                settings.topSurface_ = surfaceManager_.getSurface(topSurfaceCombo_.getSelectedIndex());
                settings.bottomSurface_ = surfaceManager_.getSurface(bottomSurfaceCombo_.getSelectedIndex());
                settings.distanceAboveTopSurface_ = (Double) umAboveTopSurfaceSpinner_.getValue();
                settings.distanceBelowBottomSurface_ = (Double) umBelowBottomSurfaceSpinner_.getValue();
                settings.useTopOrBottomFootprint_ = volumeBetweenFootprintCombo_.getSelectedItem().equals("Top surface")
                        ? FixedAreaAcquisitionSettings.FOOTPRINT_FROM_TOP : FixedAreaAcquisitionSettings.FOOTPRINT_FROM_BOTTOM;
            } else if (zStackTypeTabbedPane_.getSelectedIndex() == 2) {
                settings.spaceMode_ = FixedAreaAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK;
                settings.distanceBelowFixedSurface_ = ((Number) distanceBelowFixedSurfaceSpinner_.getValue()).doubleValue();
                settings.distanceAboveFixedSurface_ = ((Number) distanceAboveFixedSurfaceSpinner_.getValue()).doubleValue();
                settings.fixedSurface_ = surfaceManager_.getSurface(fixedDistanceSurfaceComboBox_.getSelectedIndex());
                settings.footprint_ = getFootprintObject(withinDistanceFromFootprintCombo_.getSelectedIndex());  
            }
        } else {
            settings.spaceMode_ = FixedAreaAcquisitionSettings.NO_SPACE;
        }

        settings.storePreferedValues();
        multipleAcqTable_.repaint();

       if (multiAcqManager_.isRunning()) {
          //signal acquisition settings change for dynamic updating of acquisiitons
          multiAcqManager_.signalAcqSettingsChange();
       } else {
          //estimate time needed for acquisition
          acqDurationEstimator_.calcAcqDuration(getActiveAcquisitionSettings());
       }
    }

    private void populateAcqControls(FixedAreaAcquisitionSettings settings) {
        //don't autostore outdated settings while controls are being populated
        storeAcqSettings_ = false;
        multiAcqManager_.setAcquisitionName(multiAcqSelectedIndex_, settings.name_);
        //time
        timePointsCheckBox_.setSelected(settings.timeEnabled_);
        numTimePointsSpinner_.setValue(settings.numTimePoints_);
        timeIntervalSpinner_.setValue(settings.timePointInterval_);
        timeIntevalUnitCombo_.setSelectedIndex(settings.timeIntervalUnit_);
        //space           
        acqOrderCombo_.setSelectedIndex(settings.channelsAtEverySlice_ ? 0 : 1);
        acq2D3DTabbedPane_.setSelectedIndex(settings.spaceMode_ == FixedAreaAcquisitionSettings.REGION_2D ? 0 : 1);
        zStackTypeTabbedPane_.setSelectedIndex(settings.spaceMode_ == FixedAreaAcquisitionSettings.SIMPLE_Z_STACK ? 0: 
                (settings.spaceMode_ == FixedAreaAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK ? 1 : 2));
        zStepSpinner_.setValue(settings.zStep_);
        zStartSpinner_.setValue(settings.zStart_);
        zEndSpinner_.setValue(settings.zEnd_);
        distanceBelowFixedSurfaceSpinner_.setValue(settings.distanceBelowFixedSurface_);
        distanceAboveFixedSurfaceSpinner_.setValue(settings.distanceAboveFixedSurface_);
        acqOverlapPercentSpinner_.setValue(settings.tileOverlap_);
        umAboveTopSurfaceSpinner_.setValue(settings.distanceAboveTopSurface_);
        umBelowBottomSurfaceSpinner_.setValue(settings.distanceBelowBottomSurface_);
        //select surfaces/regions
        simpleZStackFootprintCombo_.setSelectedItem(settings.footprint_);
        topSurfaceCombo_.setSelectedItem(settings.topSurface_);
        bottomSurfaceCombo_.setSelectedItem(settings.bottomSurface_);
        volumeBetweenFootprintCombo_.setSelectedIndex(settings.useTopOrBottomFootprint_);
        fixedDistanceSurfaceComboBox_.setSelectedItem(settings.fixedSurface_);
        footprint2DComboBox_.setSelectedItem(settings.footprint_);
        withinDistanceFromFootprintCombo_.setSelectedItem(settings.footprint_);

        
        //channels
        ChannelGroupCombo_.setSelectedItem(settings.channelGroup_);
        ((SimpleChannelTableModel) channelsTable_.getModel()).setChannelGroup(settings.channelGroup_);
        ((SimpleChannelTableModel) channelsTable_.getModel()).setChannels(settings.channels_);
        
        enableAcquisitionComponentsAsNeeded();

        repaint();
        storeAcqSettings_ = true;
    }

    private void addGlobalSettingsListeners() {
        globalSavingDirTextField_.getDocument().addDocumentListener(new DocumentListener() {
            @Override
            public void insertUpdate(DocumentEvent e) {
                settings_.storeSavingDirectory(globalSavingDirTextField_.getText());
            }

            @Override
            public void removeUpdate(DocumentEvent e) {
                settings_.storeSavingDirectory(globalSavingDirTextField_.getText());
            }

            @Override
            public void changedUpdate(DocumentEvent e) {
                settings_.storeSavingDirectory(globalSavingDirTextField_.getText());
            }
        });
    }

    //store values when user types text, becuase
    private void addTextEditListener(JSpinner spinner) {
        JSpinner.NumberEditor editor = (JSpinner.NumberEditor) spinner.getEditor();
        editor.getTextField().addFocusListener(new FocusAdapter() {
            @Override
            public void focusLost(FocusEvent e) {
                storeCurrentAcqSettings();
            }
        });
    }

    public void enableMultiAcquisitionControls(boolean enable) {
        addAcqButton_.setEnabled(enable);
        removeAcqButton_.setEnabled(enable);
        moveAcqDownButton_.setEnabled(enable);
        moveAcqUpButton_.setEnabled(enable);
        repaint();
    }
    
    /**
     * Channel offsets must be within 9 of eachother
     */
    public void validateChannelOffsets() {
        int minOffset = 200, maxOffset = -200;
        for (JSpinner s : offsetSpinners_) {
            minOffset = Math.min(((Number)s.getValue()).intValue(), minOffset);
            maxOffset = Math.min(((Number)s.getValue()).intValue(), maxOffset);
        }
        if (Math.abs(minOffset - maxOffset) > 9) {
            for (JSpinner s : offsetSpinners_) {
                s.setValue(Math.min(((Number) s.getValue()).intValue(), minOffset + 9));
            }
        }
        
    }

    /**
     * This method is called from within the constructor to initialize the form.
     * WARNING: Do NOT modify this code. The content of this method is always
     * regenerated by the Form Editor.
     */
    @SuppressWarnings("unchecked")
   // <editor-fold defaultstate="collapsed" desc="Generated Code">//GEN-BEGIN:initComponents
   private void initComponents() {

      zStackModeButtonGroup_ = new javax.swing.ButtonGroup();
      filterMethodButtonGroup_ = new javax.swing.ButtonGroup();
      exploreFilterMethodButtonGroup_ = new javax.swing.ButtonGroup();
      jLabel11 = new javax.swing.JLabel();
      z2DButtonGroup_ = new javax.swing.ButtonGroup();
      root_panel_ = new javax.swing.JPanel();
      exploreAcqTabbedPane_ = new javax.swing.JTabbedPane();
      explorePanel = new javax.swing.JPanel();
      exploreZStepLabel_ = new javax.swing.JLabel();
      exploreZStepSpinner_ = new javax.swing.JSpinner();
      channelGroupLabel_ = new javax.swing.JLabel();
      exploreChannelGroupCombo_ = new javax.swing.JComboBox();
      exploreOverlapLabel_ = new javax.swing.JLabel();
      exploreTileOverlapSpinner_ = new javax.swing.JSpinner();
      explorePercentLabel_ = new javax.swing.JLabel();
      exploreSavingNameLabel_ = new javax.swing.JLabel();
      exploreSavingNameTextField_ = new javax.swing.JTextField();
      newExploreWindowButton_ = new javax.swing.JButton();
      jPanel4 = new javax.swing.JPanel();
      deleteAllRegionsButton_ = new javax.swing.JButton();
      deleteSelectedRegionButton_ = new javax.swing.JButton();
      loadButton_ = new javax.swing.JButton();
      saveButton_ = new javax.swing.JButton();
      jScrollPane2 = new javax.swing.JScrollPane();
      gridTable_ = new javax.swing.JTable();
      surfacesAndGrdisLabel_ = new javax.swing.JLabel();
      acqPanel = new javax.swing.JPanel();
      acqTabbedPane_ = new javax.swing.JTabbedPane();
      timePointsTab_ = new javax.swing.JPanel();
      timePointsPanel_ = new javax.swing.JPanel();
      timeIntevalUnitCombo_ = new javax.swing.JComboBox();
      timeIntervalLabel_ = new javax.swing.JLabel();
      numTimePointsLabel_ = new javax.swing.JLabel();
      numTimePointsSpinner_ = new javax.swing.JSpinner();
      timeIntervalSpinner_ = new javax.swing.JSpinner();
      timePointsCheckBox_ = new javax.swing.JCheckBox();
      spaceTab_ = new javax.swing.JPanel();
      acq2D3DTabbedPane_ = new javax.swing.JTabbedPane();
      acq2DPanel_ = new javax.swing.JPanel();
      panel2D_ = new javax.swing.JPanel();
      footprin2DLabel_ = new javax.swing.JLabel();
      footprint2DComboBox_ = new javax.swing.JComboBox();
      collectionPlaneCombo_ = new javax.swing.JComboBox();
      collectionPlaneLabel_ = new javax.swing.JLabel();
      noCollectionPlaneButton_ = new javax.swing.JRadioButton();
      useCollectionPlaneButton_ = new javax.swing.JRadioButton();
      acq3DPanel_ = new javax.swing.JPanel();
      zStepLabel_ = new javax.swing.JLabel();
      zStepSpinner_ = new javax.swing.JSpinner();
      acqOrderLabel_ = new javax.swing.JLabel();
      acqOrderCombo_ = new javax.swing.JComboBox();
      zStackTypeTabbedPane_ = new javax.swing.JTabbedPane();
      simpleZPanel_ = new javax.swing.JPanel();
      zStartLabel = new javax.swing.JLabel();
      zEndLabel = new javax.swing.JLabel();
      jLabel2 = new javax.swing.JLabel();
      simpleZStackFootprintCombo_ = new javax.swing.JComboBox();
      zStartSpinner_ = new javax.swing.JSpinner();
      zEndSpinner_ = new javax.swing.JSpinner();
      jButton2 = new javax.swing.JButton();
      jButton3 = new javax.swing.JButton();
      volumeBetweenZPanel_ = new javax.swing.JPanel();
      topSurfaceLabel_ = new javax.swing.JLabel();
      bottomSurfaceLabel_ = new javax.swing.JLabel();
      topSurfaceCombo_ = new javax.swing.JComboBox();
      bottomSurfaceCombo_ = new javax.swing.JComboBox();
      jLabel5 = new javax.swing.JLabel();
      volumeBetweenFootprintCombo_ = new javax.swing.JComboBox();
      umAboveTopSurfaceSpinner_ = new javax.swing.JSpinner();
      umAboveVolBetweenLabel_ = new javax.swing.JLabel();
      umBelowBottomSurfaceSpinner_ = new javax.swing.JSpinner();
      umBelowVolBetweenLabel_ = new javax.swing.JLabel();
      fixedDistanceZPanel_ = new javax.swing.JPanel();
      distanceBelowSurfaceLabel_ = new javax.swing.JLabel();
      distanceBelowFixedSurfaceSpinner_ = new javax.swing.JSpinner();
      distanceAboveSurfaceLabel_ = new javax.swing.JLabel();
      distanceAboveFixedSurfaceSpinner_ = new javax.swing.JSpinner();
      umAboveLabel_ = new javax.swing.JLabel();
      umBelowLabel_ = new javax.swing.JLabel();
      fixedSurfaceLabel_ = new javax.swing.JLabel();
      fixedDistanceSurfaceComboBox_ = new javax.swing.JComboBox();
      jLabel12 = new javax.swing.JLabel();
      withinDistanceFromFootprintCombo_ = new javax.swing.JComboBox();
      acqTileOverlapLabel_ = new javax.swing.JLabel();
      acqOverlapPercentSpinner_ = new javax.swing.JSpinner();
      tileOverlapPercentLabel_ = new javax.swing.JLabel();
      ChannelsTab_ = new javax.swing.JPanel();
      jScrollPane1 = new javax.swing.JScrollPane();
      channelsTable_ = new javax.swing.JTable();
      jLabel3 = new javax.swing.JLabel();
      ChannelGroupCombo_ = new javax.swing.JComboBox();
      jPanel1 = new javax.swing.JPanel();
      runAcqButton_ = new javax.swing.JButton();
      estDurationLabel_ = new javax.swing.JLabel();
      multipleAcqScrollPane_ = new javax.swing.JScrollPane();
      multipleAcqTable_ = new javax.swing.JTable();
      moveAcqDownButton_ = new javax.swing.JButton();
      moveAcqUpButton_ = new javax.swing.JButton();
      removeAcqButton_ = new javax.swing.JButton();
      addAcqButton_ = new javax.swing.JButton();
      bottomPanel_ = new javax.swing.JPanel();
      userGuideLink_ = new javax.swing.JLabel();
      citeLink_ = new javax.swing.JLabel();
      helpButton_ = new javax.swing.JButton();
      calinrateTilingButton_ = new javax.swing.JButton();
      topPanel_ = new javax.swing.JPanel();
      exploreSavingDirLabel_ = new javax.swing.JLabel();
      globalSavingDirTextField_ = new javax.swing.JTextField();
      exploreBrowseButton_ = new javax.swing.JButton();
      openDatasetButton_ = new javax.swing.JButton();

      jLabel11.setText("jLabel11");

      getContentPane().setLayout(new javax.swing.BoxLayout(getContentPane(), javax.swing.BoxLayout.LINE_AXIS));

      exploreZStepLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      exploreZStepLabel_.setText("<html>Z-step (&mu;m):</html>");

      exploreZStepSpinner_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      exploreZStepSpinner_.setModel(new javax.swing.SpinnerNumberModel(1.0d, null, null, 1.0d));
      exploreZStepSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            exploreZStepSpinner_StateChanged(evt);
         }
      });

      channelGroupLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      channelGroupLabel_.setText("Channel Group (optional): ");

      exploreChannelGroupCombo_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      exploreChannelGroupCombo_.setModel(new ChannelComboBoxModel());

      exploreOverlapLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      exploreOverlapLabel_.setText("XY tile overlap:");

      exploreTileOverlapSpinner_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      exploreTileOverlapSpinner_.setModel(new javax.swing.SpinnerNumberModel(0.0d, 0.0d, 99.0d, 1.0d));

      explorePercentLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      explorePercentLabel_.setText("%");

      exploreSavingNameLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      exploreSavingNameLabel_.setText("Saving name: ");

      exploreSavingNameTextField_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      exploreSavingNameTextField_.setText("jTextField2");
      exploreSavingNameTextField_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            exploreSavingNameTextField_ActionPerformed(evt);
         }
      });

      newExploreWindowButton_.setFont(new java.awt.Font("Tahoma", 1, 14)); // NOI18N
      newExploreWindowButton_.setText("Explore!");
      newExploreWindowButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            newExploreWindowButton_ActionPerformed(evt);
         }
      });

      deleteAllRegionsButton_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      deleteAllRegionsButton_.setText("Delete all");
      deleteAllRegionsButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            deleteAllRegionsButton_ActionPerformed(evt);
         }
      });

      deleteSelectedRegionButton_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      deleteSelectedRegionButton_.setText("Delete selected");
      deleteSelectedRegionButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            deleteSelectedRegionButton_ActionPerformed(evt);
         }
      });

      loadButton_.setText("Load");
      loadButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            loadButton_ActionPerformed(evt);
         }
      });

      saveButton_.setText("Save");
      saveButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            saveButton_ActionPerformed(evt);
         }
      });

      gridTable_.setModel(regionManager_.createGridTableModel());
      gridTable_.setSelectionMode(javax.swing.ListSelectionModel.SINGLE_SELECTION);
      jScrollPane2.setViewportView(gridTable_);

      javax.swing.GroupLayout jPanel4Layout = new javax.swing.GroupLayout(jPanel4);
      jPanel4.setLayout(jPanel4Layout);
      jPanel4Layout.setHorizontalGroup(
         jPanel4Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addComponent(jScrollPane2)
         .addGroup(jPanel4Layout.createSequentialGroup()
            .addContainerGap()
            .addComponent(saveButton_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(loadButton_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED, 63, Short.MAX_VALUE)
            .addComponent(deleteSelectedRegionButton_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(deleteAllRegionsButton_)
            .addGap(347, 347, 347))
      );
      jPanel4Layout.setVerticalGroup(
         jPanel4Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(jPanel4Layout.createSequentialGroup()
            .addGap(20, 20, 20)
            .addComponent(jScrollPane2, javax.swing.GroupLayout.DEFAULT_SIZE, 264, Short.MAX_VALUE)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addGroup(jPanel4Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(deleteSelectedRegionButton_)
               .addComponent(deleteAllRegionsButton_)
               .addComponent(saveButton_)
               .addComponent(loadButton_))
            .addContainerGap())
      );

      surfacesAndGrdisLabel_.setFont(new java.awt.Font("Lucida Grande", 1, 18)); // NOI18N
      surfacesAndGrdisLabel_.setText("Surfaces and Grids");

      javax.swing.GroupLayout explorePanelLayout = new javax.swing.GroupLayout(explorePanel);
      explorePanel.setLayout(explorePanelLayout);
      explorePanelLayout.setHorizontalGroup(
         explorePanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(explorePanelLayout.createSequentialGroup()
            .addGroup(explorePanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addGroup(explorePanelLayout.createSequentialGroup()
                  .addContainerGap()
                  .addGroup(explorePanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
                     .addGroup(explorePanelLayout.createSequentialGroup()
                        .addComponent(exploreZStepLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(exploreZStepSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 77, javax.swing.GroupLayout.PREFERRED_SIZE)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(exploreOverlapLabel_)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(exploreTileOverlapSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 65, javax.swing.GroupLayout.PREFERRED_SIZE)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(explorePercentLabel_)
                        .addGap(36, 36, 36)
                        .addComponent(channelGroupLabel_)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(exploreChannelGroupCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, 172, javax.swing.GroupLayout.PREFERRED_SIZE))
                     .addGroup(explorePanelLayout.createSequentialGroup()
                        .addComponent(exploreSavingNameLabel_)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(exploreSavingNameTextField_, javax.swing.GroupLayout.PREFERRED_SIZE, 663, javax.swing.GroupLayout.PREFERRED_SIZE))))
               .addGroup(explorePanelLayout.createSequentialGroup()
                  .addGap(14, 14, 14)
                  .addComponent(surfacesAndGrdisLabel_))
               .addGroup(explorePanelLayout.createSequentialGroup()
                  .addContainerGap()
                  .addComponent(jPanel4, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
               .addGroup(explorePanelLayout.createSequentialGroup()
                  .addGap(343, 343, 343)
                  .addComponent(newExploreWindowButton_)))
            .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE))
      );
      explorePanelLayout.setVerticalGroup(
         explorePanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(explorePanelLayout.createSequentialGroup()
            .addGroup(explorePanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(exploreZStepSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(exploreZStepLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(channelGroupLabel_)
               .addComponent(exploreChannelGroupCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(exploreOverlapLabel_)
               .addComponent(exploreTileOverlapSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(explorePercentLabel_))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED)
            .addGroup(explorePanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(exploreSavingNameTextField_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(exploreSavingNameLabel_))
            .addGap(18, 18, 18)
            .addComponent(newExploreWindowButton_)
            .addGap(9, 9, 9)
            .addComponent(surfacesAndGrdisLabel_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(jPanel4, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE))
      );

      addTextEditListener(zStepSpinner_);

      exploreAcqTabbedPane_.addTab("Explore", explorePanel);

      acqTabbedPane_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N

      timeIntevalUnitCombo_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      timeIntevalUnitCombo_.setModel(new DefaultComboBoxModel(new String[]{"ms", "s", "min"}));
      timeIntevalUnitCombo_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            timeIntevalUnitCombo_ActionPerformed(evt);
         }
      });

      timeIntervalLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      timeIntervalLabel_.setText("Interval");

      numTimePointsLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      numTimePointsLabel_.setText("Number");

      numTimePointsSpinner_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      numTimePointsSpinner_.setModel(new javax.swing.SpinnerNumberModel(1, 1, null, 1));
      numTimePointsSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            numTimePointsSpinner_StateChanged(evt);
         }
      });

      timeIntervalSpinner_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      timeIntervalSpinner_.setModel(new javax.swing.SpinnerNumberModel(0.0d, 0.0d, null, 1.0d));
      timeIntervalSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            timeIntervalSpinner_StateChanged(evt);
         }
      });

      javax.swing.GroupLayout timePointsPanel_Layout = new javax.swing.GroupLayout(timePointsPanel_);
      timePointsPanel_.setLayout(timePointsPanel_Layout);
      timePointsPanel_Layout.setHorizontalGroup(
         timePointsPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(timePointsPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(timePointsPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING, false)
               .addGroup(timePointsPanel_Layout.createSequentialGroup()
                  .addComponent(timeIntervalLabel_)
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED)
                  .addComponent(timeIntervalSpinner_))
               .addGroup(timePointsPanel_Layout.createSequentialGroup()
                  .addComponent(numTimePointsLabel_)
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addComponent(numTimePointsSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 87, javax.swing.GroupLayout.PREFERRED_SIZE)))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(timeIntevalUnitCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, 78, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE))
      );
      timePointsPanel_Layout.setVerticalGroup(
         timePointsPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(timePointsPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(timePointsPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(numTimePointsLabel_)
               .addComponent(numTimePointsSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED)
            .addGroup(timePointsPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(timeIntervalLabel_)
               .addComponent(timeIntervalSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(timeIntevalUnitCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, 28, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addGap(0, 9, Short.MAX_VALUE))
      );

      addTextEditListener(numTimePointsSpinner_);
      addTextEditListener(timeIntervalSpinner_);

      timePointsCheckBox_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      timePointsCheckBox_.setText("Use time points");
      timePointsCheckBox_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            timePointsCheckBox_ActionPerformed(evt);
         }
      });

      javax.swing.GroupLayout timePointsTab_Layout = new javax.swing.GroupLayout(timePointsTab_);
      timePointsTab_.setLayout(timePointsTab_Layout);
      timePointsTab_Layout.setHorizontalGroup(
         timePointsTab_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(timePointsTab_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(timePointsTab_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addComponent(timePointsPanel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(timePointsCheckBox_))
            .addContainerGap(556, Short.MAX_VALUE))
      );
      timePointsTab_Layout.setVerticalGroup(
         timePointsTab_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(timePointsTab_Layout.createSequentialGroup()
            .addGap(6, 6, 6)
            .addComponent(timePointsCheckBox_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(timePointsPanel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addContainerGap(192, Short.MAX_VALUE))
      );

      for (Component c : timePointsPanel_.getComponents()) {
         c.setEnabled(false);
      }

      acqTabbedPane_.addTab("Time", timePointsTab_);

      footprin2DLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      footprin2DLabel_.setText("Surface/Grid XY Footprint:");

      footprint2DComboBox_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      footprint2DComboBox_.setModel(createSurfaceAndRegionComboBoxModel(true,true));
      footprint2DComboBox_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            footprint2DComboBox_ActionPerformed(evt);
         }
      });

      collectionPlaneCombo_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      collectionPlaneCombo_.setModel(createSurfaceAndRegionComboBoxModel(true,false));
      collectionPlaneCombo_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            collectionPlaneCombo_ActionPerformed(evt);
         }
      });

      z2DButtonGroup_.add(noCollectionPlaneButton_);
      noCollectionPlaneButton_.setText("Use current Z position");
      noCollectionPlaneButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            noCollectionPlaneButton_ActionPerformed(evt);
         }
      });

      z2DButtonGroup_.add(useCollectionPlaneButton_);
      useCollectionPlaneButton_.setText("Get Z position from surface");

      javax.swing.GroupLayout panel2D_Layout = new javax.swing.GroupLayout(panel2D_);
      panel2D_.setLayout(panel2D_Layout);
      panel2D_Layout.setHorizontalGroup(
         panel2D_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(panel2D_Layout.createSequentialGroup()
            .addGroup(panel2D_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addGroup(panel2D_Layout.createSequentialGroup()
                  .addComponent(useCollectionPlaneButton_)
                  .addGroup(panel2D_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
                     .addGroup(panel2D_Layout.createSequentialGroup()
                        .addGap(36, 36, 36)
                        .addComponent(collectionPlaneLabel_))
                     .addGroup(panel2D_Layout.createSequentialGroup()
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(collectionPlaneCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, 238, javax.swing.GroupLayout.PREFERRED_SIZE))))
               .addComponent(noCollectionPlaneButton_)
               .addGroup(panel2D_Layout.createSequentialGroup()
                  .addContainerGap()
                  .addComponent(footprin2DLabel_)
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addComponent(footprint2DComboBox_, javax.swing.GroupLayout.PREFERRED_SIZE, 241, javax.swing.GroupLayout.PREFERRED_SIZE)))
            .addContainerGap(18, Short.MAX_VALUE))
      );
      panel2D_Layout.setVerticalGroup(
         panel2D_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(panel2D_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(panel2D_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(footprin2DLabel_)
               .addComponent(footprint2DComboBox_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(noCollectionPlaneButton_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addGroup(panel2D_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(useCollectionPlaneButton_)
               .addComponent(collectionPlaneCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(collectionPlaneLabel_)
            .addContainerGap(8, Short.MAX_VALUE))
      );

      javax.swing.GroupLayout acq2DPanel_Layout = new javax.swing.GroupLayout(acq2DPanel_);
      acq2DPanel_.setLayout(acq2DPanel_Layout);
      acq2DPanel_Layout.setHorizontalGroup(
         acq2DPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(acq2DPanel_Layout.createSequentialGroup()
            .addComponent(panel2D_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addGap(0, 276, Short.MAX_VALUE))
      );
      acq2DPanel_Layout.setVerticalGroup(
         acq2DPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(acq2DPanel_Layout.createSequentialGroup()
            .addComponent(panel2D_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addGap(0, 112, Short.MAX_VALUE))
      );

      acq2D3DTabbedPane_.addTab("2D", acq2DPanel_);

      zStepLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      zStepLabel_.setText("<html>Z-step (&mu;m):</html>");

      zStepSpinner_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      zStepSpinner_.setModel(new javax.swing.SpinnerNumberModel(1.0d, null, null, 1.0d));
      zStepSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            zStepSpinner_StateChanged(evt);
         }
      });

      acqOrderLabel_.setText("Order:");

      acqOrderCombo_.setModel(new javax.swing.DefaultComboBoxModel(new String[] { "Channels at each Z slice", "Z stacks for each channel" }));
      acqOrderCombo_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            acqOrderCombo_ActionPerformed(evt);
         }
      });

      zStartLabel.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      zStartLabel.setText("<html>Z-start (&mu;m)</html>");

      zEndLabel.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      zEndLabel.setText("<html>Z-end (&mu;m)</html>");

      jLabel2.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      jLabel2.setText("Surface/Grid XY footprint:");

      simpleZStackFootprintCombo_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      simpleZStackFootprintCombo_.setModel(createSurfaceAndRegionComboBoxModel(true,true));
      simpleZStackFootprintCombo_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            simpleZStackFootprintCombo_ActionPerformed(evt);
         }
      });

      zStartSpinner_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      zStartSpinner_.setModel(new javax.swing.SpinnerNumberModel(0.0d, null, null, 1.0d));
      zStartSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            zStartSpinner_StateChanged(evt);
         }
      });

      zEndSpinner_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      zEndSpinner_.setModel(new javax.swing.SpinnerNumberModel(0.0d, null, null, 1.0d));
      zEndSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            zEndSpinner_StateChanged(evt);
         }
      });

      jButton2.setText("Set current Z");
      jButton2.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            jButton2ActionPerformed(evt);
         }
      });

      jButton3.setText("Set current Z");
      jButton3.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            jButton3ActionPerformed(evt);
         }
      });

      javax.swing.GroupLayout simpleZPanel_Layout = new javax.swing.GroupLayout(simpleZPanel_);
      simpleZPanel_.setLayout(simpleZPanel_Layout);
      simpleZPanel_Layout.setHorizontalGroup(
         simpleZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(simpleZPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(simpleZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING, false)
               .addGroup(simpleZPanel_Layout.createSequentialGroup()
                  .addComponent(jLabel2)
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addComponent(simpleZStackFootprintCombo_, 0, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE))
               .addGroup(simpleZPanel_Layout.createSequentialGroup()
                  .addGroup(simpleZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.TRAILING, false)
                     .addGroup(javax.swing.GroupLayout.Alignment.LEADING, simpleZPanel_Layout.createSequentialGroup()
                        .addComponent(zEndLabel, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
                        .addGap(18, 18, 18)
                        .addComponent(zEndSpinner_))
                     .addGroup(javax.swing.GroupLayout.Alignment.LEADING, simpleZPanel_Layout.createSequentialGroup()
                        .addComponent(zStartLabel, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED)
                        .addComponent(zStartSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 120, javax.swing.GroupLayout.PREFERRED_SIZE)))
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addGroup(simpleZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
                     .addComponent(jButton2)
                     .addComponent(jButton3))))
            .addContainerGap(373, Short.MAX_VALUE))
      );
      simpleZPanel_Layout.setVerticalGroup(
         simpleZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(simpleZPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(simpleZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(zStartLabel, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(zStartSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(jButton2))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addGroup(simpleZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(zEndLabel, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(zEndSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(jButton3))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED)
            .addGroup(simpleZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(jLabel2)
               .addComponent(simpleZStackFootprintCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addContainerGap(29, Short.MAX_VALUE))
      );

      addTextEditListener(zStartSpinner_);
      addTextEditListener(zEndSpinner_);

      zStackTypeTabbedPane_.addTab("Cuboid volume", simpleZPanel_);
      for (Component c : simpleZPanel_.getComponents()) {
         c.setEnabled(false);
      }

      topSurfaceLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      topSurfaceLabel_.setText("Z-start");

      bottomSurfaceLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      bottomSurfaceLabel_.setText("Z-end");

      topSurfaceCombo_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      topSurfaceCombo_.setModel(createSurfaceAndRegionComboBoxModel(true,false));
      topSurfaceCombo_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            topSurfaceCombo_ActionPerformed(evt);
         }
      });

      bottomSurfaceCombo_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      bottomSurfaceCombo_.setModel(createSurfaceAndRegionComboBoxModel(true,false));
      bottomSurfaceCombo_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            bottomSurfaceCombo_ActionPerformed(evt);
         }
      });

      jLabel5.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      jLabel5.setText("XY footprint from:");

      volumeBetweenFootprintCombo_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      volumeBetweenFootprintCombo_.setModel(new javax.swing.DefaultComboBoxModel(new String[] { "Top surface", "Bottom surface" }));
      volumeBetweenFootprintCombo_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            volumeBetweenFootprintCombo_ActionPerformed(evt);
         }
      });

      umAboveTopSurfaceSpinner_.setModel(new javax.swing.SpinnerNumberModel(0.0d, 0.0d, null, 1.0d));
      umAboveTopSurfaceSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            umAboveTopSurfaceSpinner_StateChanged(evt);
         }
      });

      umAboveVolBetweenLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      umAboveVolBetweenLabel_.setText("<html>&mu;m above</html>");

      umBelowBottomSurfaceSpinner_.setModel(new javax.swing.SpinnerNumberModel(0.0d, 0.0d, null, 1.0d));
      umBelowBottomSurfaceSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            umBelowBottomSurfaceSpinner_StateChanged(evt);
         }
      });

      umBelowVolBetweenLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      umBelowVolBetweenLabel_.setText("<html>&mu;m below</html>");

      javax.swing.GroupLayout volumeBetweenZPanel_Layout = new javax.swing.GroupLayout(volumeBetweenZPanel_);
      volumeBetweenZPanel_.setLayout(volumeBetweenZPanel_Layout);
      volumeBetweenZPanel_Layout.setHorizontalGroup(
         volumeBetweenZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(volumeBetweenZPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(volumeBetweenZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addGroup(volumeBetweenZPanel_Layout.createSequentialGroup()
                  .addGroup(volumeBetweenZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
                     .addComponent(topSurfaceLabel_)
                     .addComponent(bottomSurfaceLabel_))
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addGroup(volumeBetweenZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING, false)
                     .addComponent(umAboveTopSurfaceSpinner_, javax.swing.GroupLayout.DEFAULT_SIZE, 71, Short.MAX_VALUE)
                     .addComponent(umBelowBottomSurfaceSpinner_))
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addGroup(volumeBetweenZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
                     .addComponent(umAboveVolBetweenLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
                     .addComponent(umBelowVolBetweenLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addGroup(volumeBetweenZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING, false)
                     .addComponent(topSurfaceCombo_, 0, 166, Short.MAX_VALUE)
                     .addComponent(bottomSurfaceCombo_, 0, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)))
               .addGroup(volumeBetweenZPanel_Layout.createSequentialGroup()
                  .addComponent(jLabel5)
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addComponent(volumeBetweenFootprintCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)))
            .addContainerGap(353, Short.MAX_VALUE))
      );
      volumeBetweenZPanel_Layout.setVerticalGroup(
         volumeBetweenZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(volumeBetweenZPanel_Layout.createSequentialGroup()
            .addGroup(volumeBetweenZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(topSurfaceLabel_)
               .addComponent(topSurfaceCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(umAboveTopSurfaceSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(umAboveVolBetweenLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED)
            .addGroup(volumeBetweenZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(bottomSurfaceLabel_)
               .addComponent(bottomSurfaceCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(umBelowBottomSurfaceSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(umBelowVolBetweenLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED)
            .addGroup(volumeBetweenZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(jLabel5)
               .addComponent(volumeBetweenFootprintCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addGap(0, 35, Short.MAX_VALUE))
      );

      zStackTypeTabbedPane_.addTab("Volume between surfaces", volumeBetweenZPanel_);
      for (Component c : volumeBetweenZPanel_.getComponents()) {
         c.setEnabled(false);
      }

      distanceBelowSurfaceLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      distanceBelowSurfaceLabel_.setText("Z-end");

      distanceBelowFixedSurfaceSpinner_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      distanceBelowFixedSurfaceSpinner_.setModel(new javax.swing.SpinnerNumberModel(0.0d, 0.0d, null, 0.001d));
      distanceBelowFixedSurfaceSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            distanceBelowFixedSurfaceSpinner_StateChanged(evt);
         }
      });

      distanceAboveSurfaceLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      distanceAboveSurfaceLabel_.setText("Z-start");

      distanceAboveFixedSurfaceSpinner_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      distanceAboveFixedSurfaceSpinner_.setModel(new javax.swing.SpinnerNumberModel(0.0d, 0.0d, null, 0.001d));
      distanceAboveFixedSurfaceSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            distanceAboveFixedSurfaceSpinner_StateChanged(evt);
         }
      });

      umAboveLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      umAboveLabel_.setText("<html>&mu;m above</html>");

      umBelowLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      umBelowLabel_.setText("<html>&mu;m below</html>");

      fixedSurfaceLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      fixedSurfaceLabel_.setText("Surface: ");

      fixedDistanceSurfaceComboBox_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      fixedDistanceSurfaceComboBox_.setModel(createSurfaceAndRegionComboBoxModel(true,false));
      fixedDistanceSurfaceComboBox_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            fixedDistanceSurfaceComboBox_ActionPerformed(evt);
         }
      });

      jLabel12.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      jLabel12.setText("Surface/Grid XY footprint:");

      withinDistanceFromFootprintCombo_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      withinDistanceFromFootprintCombo_.setModel(createSurfaceAndRegionComboBoxModel(true,true));
      withinDistanceFromFootprintCombo_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            withinDistanceFromFootprintCombo_ActionPerformed(evt);
         }
      });

      javax.swing.GroupLayout fixedDistanceZPanel_Layout = new javax.swing.GroupLayout(fixedDistanceZPanel_);
      fixedDistanceZPanel_.setLayout(fixedDistanceZPanel_Layout);
      fixedDistanceZPanel_Layout.setHorizontalGroup(
         fixedDistanceZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(fixedDistanceZPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(fixedDistanceZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addGroup(fixedDistanceZPanel_Layout.createSequentialGroup()
                  .addGroup(fixedDistanceZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
                     .addGroup(javax.swing.GroupLayout.Alignment.TRAILING, fixedDistanceZPanel_Layout.createSequentialGroup()
                        .addComponent(distanceAboveSurfaceLabel_)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED)
                        .addComponent(distanceAboveFixedSurfaceSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 84, javax.swing.GroupLayout.PREFERRED_SIZE))
                     .addGroup(fixedDistanceZPanel_Layout.createSequentialGroup()
                        .addGap(3, 3, 3)
                        .addComponent(distanceBelowSurfaceLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, 41, javax.swing.GroupLayout.PREFERRED_SIZE)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED)
                        .addComponent(distanceBelowFixedSurfaceSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 81, javax.swing.GroupLayout.PREFERRED_SIZE)))
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addGroup(fixedDistanceZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
                     .addComponent(umAboveLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
                     .addComponent(umBelowLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
                  .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE))
               .addGroup(fixedDistanceZPanel_Layout.createSequentialGroup()
                  .addGroup(fixedDistanceZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING, false)
                     .addGroup(fixedDistanceZPanel_Layout.createSequentialGroup()
                        .addComponent(jLabel12)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(withinDistanceFromFootprintCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, 161, javax.swing.GroupLayout.PREFERRED_SIZE))
                     .addGroup(fixedDistanceZPanel_Layout.createSequentialGroup()
                        .addComponent(fixedSurfaceLabel_)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(fixedDistanceSurfaceComboBox_, 0, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)))
                  .addGap(0, 385, Short.MAX_VALUE))))
      );
      fixedDistanceZPanel_Layout.setVerticalGroup(
         fixedDistanceZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(fixedDistanceZPanel_Layout.createSequentialGroup()
            .addGroup(fixedDistanceZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(distanceAboveSurfaceLabel_)
               .addComponent(distanceAboveFixedSurfaceSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(umAboveLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addGap(3, 3, 3)
            .addGroup(fixedDistanceZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(distanceBelowSurfaceLabel_)
               .addComponent(distanceBelowFixedSurfaceSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(umBelowLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addGroup(fixedDistanceZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(fixedSurfaceLabel_)
               .addComponent(fixedDistanceSurfaceComboBox_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addGroup(fixedDistanceZPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(jLabel12)
               .addComponent(withinDistanceFromFootprintCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addGap(0, 15, Short.MAX_VALUE))
      );

      addTextEditListener(distanceBelowFixedSurfaceSpinner_);
      addTextEditListener(distanceAboveFixedSurfaceSpinner_);

      zStackTypeTabbedPane_.addTab("Within distance from surface", fixedDistanceZPanel_);

      javax.swing.GroupLayout acq3DPanel_Layout = new javax.swing.GroupLayout(acq3DPanel_);
      acq3DPanel_.setLayout(acq3DPanel_Layout);
      acq3DPanel_Layout.setHorizontalGroup(
         acq3DPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(acq3DPanel_Layout.createSequentialGroup()
            .addGap(14, 14, 14)
            .addComponent(zStepLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(zStepSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 77, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addGap(18, 18, 18)
            .addComponent(acqOrderLabel_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(acqOrderCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, 207, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE))
         .addGroup(acq3DPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addComponent(zStackTypeTabbedPane_))
      );
      acq3DPanel_Layout.setVerticalGroup(
         acq3DPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(acq3DPanel_Layout.createSequentialGroup()
            .addGroup(acq3DPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(zStepSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(zStepLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(acqOrderCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(acqOrderLabel_))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(zStackTypeTabbedPane_, javax.swing.GroupLayout.PREFERRED_SIZE, 186, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addGap(0, 0, 0))
      );

      addTextEditListener(zStepSpinner_);

      acq2D3DTabbedPane_.addTab("3D", acq3DPanel_);

      acqTileOverlapLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      acqTileOverlapLabel_.setText("XY tile overlap:");

      acqOverlapPercentSpinner_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      acqOverlapPercentSpinner_.setModel(new javax.swing.SpinnerNumberModel(5.0d, 0.0d, 99.0d, 1.0d));
      acqOverlapPercentSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            acqOverlapPercentSpinner_StateChanged(evt);
         }
      });

      tileOverlapPercentLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      tileOverlapPercentLabel_.setText("%");

      javax.swing.GroupLayout spaceTab_Layout = new javax.swing.GroupLayout(spaceTab_);
      spaceTab_.setLayout(spaceTab_Layout);
      spaceTab_Layout.setHorizontalGroup(
         spaceTab_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(spaceTab_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(spaceTab_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addGroup(spaceTab_Layout.createSequentialGroup()
                  .addGap(6, 6, 6)
                  .addComponent(acqTileOverlapLabel_)
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addComponent(acqOverlapPercentSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 58, javax.swing.GroupLayout.PREFERRED_SIZE)
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addComponent(tileOverlapPercentLabel_))
               .addComponent(acq2D3DTabbedPane_, javax.swing.GroupLayout.PREFERRED_SIZE, 764, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addContainerGap(30, Short.MAX_VALUE))
      );
      spaceTab_Layout.setVerticalGroup(
         spaceTab_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(spaceTab_Layout.createSequentialGroup()
            .addComponent(acq2D3DTabbedPane_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addGroup(spaceTab_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(acqTileOverlapLabel_)
               .addComponent(acqOverlapPercentSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(tileOverlapPercentLabel_))
            .addContainerGap())
      );

      acqTabbedPane_.addTab("Space", spaceTab_);

      jScrollPane1.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N

      channelsTable_.setModel(new SimpleChannelTableModel(null, true)
      );
      channelsTable_.getTableHeader().addMouseListener(new MouseAdapter() {
         @Override
         public void mouseClicked(MouseEvent e) {
            int col = channelsTable_.columnAtPoint(e.getPoint());
            if (col ==0) {
               //Select all
               ((SimpleChannelTableModel) channelsTable_.getModel()).selectAllChannels();
            } else if(col == 2) {
               //set all exposures to exposure of first
               ((SimpleChannelTableModel) channelsTable_.getModel()).synchronizeExposures();
            }
         }
      });
      jScrollPane1.setViewportView(channelsTable_);

      jLabel3.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      jLabel3.setText("Channel group:");

      ChannelGroupCombo_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      ChannelGroupCombo_.setModel(new ChannelComboBoxModel());
      ChannelGroupCombo_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            ChannelGroupCombo_ActionPerformed(evt);
         }
      });

      javax.swing.GroupLayout ChannelsTab_Layout = new javax.swing.GroupLayout(ChannelsTab_);
      ChannelsTab_.setLayout(ChannelsTab_Layout);
      ChannelsTab_Layout.setHorizontalGroup(
         ChannelsTab_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addComponent(jScrollPane1, javax.swing.GroupLayout.DEFAULT_SIZE, 800, Short.MAX_VALUE)
         .addGroup(ChannelsTab_Layout.createSequentialGroup()
            .addComponent(jLabel3)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(ChannelGroupCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, 171, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addGap(0, 0, Short.MAX_VALUE))
      );
      ChannelsTab_Layout.setVerticalGroup(
         ChannelsTab_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(javax.swing.GroupLayout.Alignment.TRAILING, ChannelsTab_Layout.createSequentialGroup()
            .addGroup(ChannelsTab_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(jLabel3)
               .addComponent(ChannelGroupCombo_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(jScrollPane1, javax.swing.GroupLayout.DEFAULT_SIZE, 277, Short.MAX_VALUE))
      );

      acqTabbedPane_.addTab("Channels", ChannelsTab_);

      runAcqButton_.setFont(new java.awt.Font("Tahoma", 1, 14)); // NOI18N
      runAcqButton_.setText("Run acquisition(s)");
      runAcqButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            runAcqButton_ActionPerformed(evt);
         }
      });

      estDurationLabel_.setText("Estimated duration: ");

      javax.swing.GroupLayout jPanel1Layout = new javax.swing.GroupLayout(jPanel1);
      jPanel1.setLayout(jPanel1Layout);
      jPanel1Layout.setHorizontalGroup(
         jPanel1Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(jPanel1Layout.createSequentialGroup()
            .addContainerGap()
            .addComponent(estDurationLabel_)
            .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE))
         .addGroup(jPanel1Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
            .addGroup(jPanel1Layout.createSequentialGroup()
               .addGap(320, 320, 320)
               .addComponent(runAcqButton_)
               .addContainerGap(320, Short.MAX_VALUE)))
      );
      jPanel1Layout.setVerticalGroup(
         jPanel1Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(jPanel1Layout.createSequentialGroup()
            .addContainerGap()
            .addComponent(estDurationLabel_)
            .addContainerGap(19, Short.MAX_VALUE))
         .addGroup(jPanel1Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
            .addGroup(jPanel1Layout.createSequentialGroup()
               .addContainerGap()
               .addComponent(runAcqButton_)
               .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)))
      );

      multipleAcqScrollPane_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N

      multipleAcqTable_.setModel(new MultipleAcquisitionTableModel(multiAcqManager_,this));
      multipleAcqTable_.setSelectionMode(javax.swing.ListSelectionModel.SINGLE_SELECTION);
      multipleAcqScrollPane_.setViewportView(multipleAcqTable_);

      moveAcqDownButton_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      moveAcqDownButton_.setText("⬇");
      moveAcqDownButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            moveAcqDownButton_ActionPerformed(evt);
         }
      });

      moveAcqUpButton_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      moveAcqUpButton_.setText("⬆");
      moveAcqUpButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            moveAcqUpButton_ActionPerformed(evt);
         }
      });

      removeAcqButton_.setFont(new java.awt.Font("Tahoma", 1, 14)); // NOI18N
      removeAcqButton_.setText("-");
      removeAcqButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            removeAcqButton_ActionPerformed(evt);
         }
      });

      addAcqButton_.setFont(new java.awt.Font("Tahoma", 1, 14)); // NOI18N
      addAcqButton_.setText("+");
      addAcqButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            addAcqButton_ActionPerformed(evt);
         }
      });

      javax.swing.GroupLayout acqPanelLayout = new javax.swing.GroupLayout(acqPanel);
      acqPanel.setLayout(acqPanelLayout);
      acqPanelLayout.setHorizontalGroup(
         acqPanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(acqPanelLayout.createSequentialGroup()
            .addContainerGap()
            .addGroup(acqPanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addGroup(acqPanelLayout.createSequentialGroup()
                  .addComponent(acqTabbedPane_)
                  .addContainerGap())
               .addGroup(acqPanelLayout.createSequentialGroup()
                  .addComponent(jPanel1, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)
                  .addGap(16, 16, 16))
               .addGroup(acqPanelLayout.createSequentialGroup()
                  .addComponent(multipleAcqScrollPane_, javax.swing.GroupLayout.PREFERRED_SIZE, 726, javax.swing.GroupLayout.PREFERRED_SIZE)
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addGroup(acqPanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.TRAILING, false)
                     .addComponent(moveAcqUpButton_, javax.swing.GroupLayout.Alignment.LEADING, javax.swing.GroupLayout.PREFERRED_SIZE, 1, Short.MAX_VALUE)
                     .addComponent(addAcqButton_, javax.swing.GroupLayout.PREFERRED_SIZE, 43, javax.swing.GroupLayout.PREFERRED_SIZE))
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addGroup(acqPanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING, false)
                     .addComponent(removeAcqButton_, javax.swing.GroupLayout.PREFERRED_SIZE, 40, javax.swing.GroupLayout.PREFERRED_SIZE)
                     .addComponent(moveAcqDownButton_, javax.swing.GroupLayout.PREFERRED_SIZE, 40, javax.swing.GroupLayout.PREFERRED_SIZE))
                  .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE))))
      );
      acqPanelLayout.setVerticalGroup(
         acqPanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(acqPanelLayout.createSequentialGroup()
            .addGroup(acqPanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addComponent(multipleAcqScrollPane_, javax.swing.GroupLayout.DEFAULT_SIZE, 68, Short.MAX_VALUE)
               .addGroup(acqPanelLayout.createSequentialGroup()
                  .addGroup(acqPanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
                     .addComponent(addAcqButton_)
                     .addComponent(removeAcqButton_))
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addGroup(acqPanelLayout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
                     .addComponent(moveAcqUpButton_)
                     .addComponent(moveAcqDownButton_))))
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(jPanel1, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(acqTabbedPane_, javax.swing.GroupLayout.PREFERRED_SIZE, 356, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addGap(0, 0, 0))
      );

      exploreAcqTabbedPane_.addTab("Acquisition(s)", acqPanel);

      userGuideLink_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      userGuideLink_.setText("<html><a href=\\\"https://micro-manager.org/wiki/MicroMagellan\\\">Micro-Magellan User Guide</a></html>");

      citeLink_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      citeLink_.setText("<html><a href=\\\"http://www.nature.com/nmeth/journal/v13/n10/full/nmeth.3991.html\\\">Cite Micro-Magellan</a></html>");

      helpButton_.setBackground(new java.awt.Color(200, 255, 200));
      helpButton_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      helpButton_.setText("Setup");
      helpButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            helpButton_ActionPerformed(evt);
         }
      });

      calinrateTilingButton_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      calinrateTilingButton_.setText("Calibrate tiling");
      calinrateTilingButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            calinrateTilingButton_ActionPerformed(evt);
         }
      });

      javax.swing.GroupLayout bottomPanel_Layout = new javax.swing.GroupLayout(bottomPanel_);
      bottomPanel_.setLayout(bottomPanel_Layout);
      bottomPanel_Layout.setHorizontalGroup(
         bottomPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(bottomPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addComponent(helpButton_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(calinrateTilingButton_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)
            .addComponent(userGuideLink_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addGap(113, 113, 113)
            .addComponent(citeLink_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addGap(94, 94, 94))
      );
      bottomPanel_Layout.setVerticalGroup(
         bottomPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(bottomPanel_Layout.createSequentialGroup()
            .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)
            .addGroup(bottomPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(calinrateTilingButton_)
               .addComponent(helpButton_)
               .addComponent(citeLink_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(userGuideLink_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)))
      );

      exploreSavingDirLabel_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      exploreSavingDirLabel_.setText("Saving directory: ");

      globalSavingDirTextField_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      globalSavingDirTextField_.setText("jTextField1");

      exploreBrowseButton_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      exploreBrowseButton_.setText("Browse");
      exploreBrowseButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            exploreBrowseButton_ActionPerformed(evt);
         }
      });

      openDatasetButton_.setFont(new java.awt.Font("Tahoma", 0, 14)); // NOI18N
      openDatasetButton_.setText("Open dataset");
      openDatasetButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            openDatasetButton_ActionPerformed(evt);
         }
      });

      javax.swing.GroupLayout topPanel_Layout = new javax.swing.GroupLayout(topPanel_);
      topPanel_.setLayout(topPanel_Layout);
      topPanel_Layout.setHorizontalGroup(
         topPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(javax.swing.GroupLayout.Alignment.TRAILING, topPanel_Layout.createSequentialGroup()
            .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)
            .addComponent(exploreBrowseButton_)
            .addGap(39, 39, 39)
            .addComponent(openDatasetButton_)
            .addContainerGap())
         .addGroup(topPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
            .addGroup(topPanel_Layout.createSequentialGroup()
               .addContainerGap()
               .addComponent(exploreSavingDirLabel_)
               .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
               .addComponent(globalSavingDirTextField_, javax.swing.GroupLayout.DEFAULT_SIZE, 453, Short.MAX_VALUE)
               .addGap(265, 265, 265)))
      );
      topPanel_Layout.setVerticalGroup(
         topPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(topPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(topPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(exploreBrowseButton_)
               .addComponent(openDatasetButton_))
            .addContainerGap(14, Short.MAX_VALUE))
         .addGroup(topPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
            .addGroup(topPanel_Layout.createSequentialGroup()
               .addContainerGap()
               .addGroup(topPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING, false)
                  .addComponent(exploreSavingDirLabel_, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)
                  .addComponent(globalSavingDirTextField_))
               .addContainerGap(16, Short.MAX_VALUE)))
      );

      javax.swing.GroupLayout root_panel_Layout = new javax.swing.GroupLayout(root_panel_);
      root_panel_.setLayout(root_panel_Layout);
      root_panel_Layout.setHorizontalGroup(
         root_panel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(javax.swing.GroupLayout.Alignment.TRAILING, root_panel_Layout.createSequentialGroup()
            .addGap(0, 0, Short.MAX_VALUE)
            .addComponent(exploreAcqTabbedPane_, javax.swing.GroupLayout.PREFERRED_SIZE, 844, javax.swing.GroupLayout.PREFERRED_SIZE))
         .addGroup(root_panel_Layout.createSequentialGroup()
            .addContainerGap()
            .addGroup(root_panel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addGroup(root_panel_Layout.createSequentialGroup()
                  .addComponent(bottomPanel_, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)
                  .addContainerGap())
               .addComponent(topPanel_, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)))
      );
      root_panel_Layout.setVerticalGroup(
         root_panel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(javax.swing.GroupLayout.Alignment.TRAILING, root_panel_Layout.createSequentialGroup()
            .addComponent(topPanel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(exploreAcqTabbedPane_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(bottomPanel_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addContainerGap())
      );

      getContentPane().add(root_panel_);

      pack();
   }// </editor-fold>//GEN-END:initComponents

   private void runAcqButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_runAcqButton_ActionPerformed
       //run acquisition
       new Thread(new Runnable() {
           @Override
           public void run() {
               eng_.runFixedAreaAcquisition(multiAcqManager_.getAcquisitionSettings(multipleAcqTable_.getSelectedRow()));
           }
       }).start();
   }//GEN-LAST:event_runAcqButton_ActionPerformed

   private void newExploreWindowButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_newExploreWindowButton_ActionPerformed
       ExploreAcqSettings settings = new ExploreAcqSettings(
               ((Number) exploreZStepSpinner_.getValue()).doubleValue(), (Double) exploreTileOverlapSpinner_.getValue(),
               globalSavingDirTextField_.getText(), exploreSavingNameTextField_.getText(), (String) exploreChannelGroupCombo_.getSelectedItem());
       eng_.runExploreAcquisition(settings);
   }//GEN-LAST:event_newExploreWindowButton_ActionPerformed

   private void exploreZStepSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_exploreZStepSpinner_StateChanged
   }//GEN-LAST:event_exploreZStepSpinner_StateChanged

   private void exploreBrowseButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_exploreBrowseButton_ActionPerformed
       String root = "";
       if (globalSavingDirTextField_.getText() != null && !globalSavingDirTextField_.getText().equals("")) {
           root = globalSavingDirTextField_.getText();
       }
       JFileChooser chooser = new JFileChooser(root);
       chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY);
       int option = chooser.showSaveDialog(this);
       if (option != JFileChooser.APPROVE_OPTION) {
           return;
       }
       File f = chooser.getSelectedFile();
       if (!f.isDirectory()) {
           f = f.getParentFile();
       }
       globalSavingDirTextField_.setText(f.getAbsolutePath());
   }//GEN-LAST:event_exploreBrowseButton_ActionPerformed

   private void exploreSavingNameTextField_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_exploreSavingNameTextField_ActionPerformed
   }//GEN-LAST:event_exploreSavingNameTextField_ActionPerformed

   private void calinrateTilingButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_calinrateTilingButton_ActionPerformed
       new AffineGUI();
   }//GEN-LAST:event_calinrateTilingButton_ActionPerformed

   private void openDatasetButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_openDatasetButton_ActionPerformed
       File selectedFile = null;
      if (JavaUtils.isMac()) {
         System.setProperty("apple.awt.fileDialogForDirectories", "true");
         FileDialog fd = new FileDialog(this, "Select Magellan dataset to load", FileDialog.LOAD);

         fd.setVisible(true);
         if (fd.getFile() != null) {
            selectedFile = new File(fd.getDirectory() + File.separator + fd.getFile());
            selectedFile = new File(selectedFile.getAbsolutePath());
         }
         fd.dispose();
         System.setProperty("apple.awt.fileDialogForDirectories", "false");
      } else {
         JFileChooser fc = new JFileChooser(globalSavingDirTextField_.getText());
         fc.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY);
         fc.setDialogTitle("Select Magellan dataset to load");
         int returnVal = fc.showOpenDialog(this);
         if (returnVal == JFileChooser.APPROVE_OPTION) {
            selectedFile = fc.getSelectedFile();
         }
      }
      if (selectedFile == null) {
         return; //canceled
      }
      final File finalFile = selectedFile;
      new Thread(new Runnable() {
         @Override
         public void run() {
            new LoadedAcquisitionData(finalFile.toString());
         }
      }).start();
      
   }//GEN-LAST:event_openDatasetButton_ActionPerformed

   private void helpButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_helpButton_ActionPerformed
      new StartupHelpWindow();
   }//GEN-LAST:event_helpButton_ActionPerformed

   private void moveAcqDownButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_moveAcqDownButton_ActionPerformed
      int move = multiAcqManager_.moveDown(multipleAcqTable_.getSelectedRow());
      multipleAcqTable_.getSelectionModel().setSelectionInterval(multiAcqSelectedIndex_ + move, multiAcqSelectedIndex_ + move);
      multipleAcqTable_.repaint();
   }//GEN-LAST:event_moveAcqDownButton_ActionPerformed

   private void moveAcqUpButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_moveAcqUpButton_ActionPerformed
      int move = multiAcqManager_.moveUp(multipleAcqTable_.getSelectedRow());
      multipleAcqTable_.getSelectionModel().setSelectionInterval(multiAcqSelectedIndex_ + move, multiAcqSelectedIndex_ + move);
      multipleAcqTable_.repaint();
   }//GEN-LAST:event_moveAcqUpButton_ActionPerformed

   private void removeAcqButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_removeAcqButton_ActionPerformed
      multiAcqManager_.remove(multipleAcqTable_.getSelectedRow());
      ((MultipleAcquisitionTableModel) multipleAcqTable_.getModel()).fireTableDataChanged();
      multipleAcqTable_.repaint();
   }//GEN-LAST:event_removeAcqButton_ActionPerformed

   private void addAcqButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_addAcqButton_ActionPerformed
      multiAcqManager_.addNew();
      ((MultipleAcquisitionTableModel) multipleAcqTable_.getModel()).fireTableDataChanged();
      multipleAcqTable_.repaint();
   }//GEN-LAST:event_addAcqButton_ActionPerformed

   private void ChannelGroupCombo_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_ChannelGroupCombo_ActionPerformed
      ((SimpleChannelTableModel) channelsTable_.getModel()).setChannelGroup((String) ChannelGroupCombo_.getSelectedItem());
      ((SimpleChannelTableModel) channelsTable_.getModel()).fireTableDataChanged();
      acquisitionSettingsChanged();
   }//GEN-LAST:event_ChannelGroupCombo_ActionPerformed

   private void acqOrderCombo_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_acqOrderCombo_ActionPerformed
      acquisitionSettingsChanged();
   }//GEN-LAST:event_acqOrderCombo_ActionPerformed

   private void acqOverlapPercentSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_acqOverlapPercentSpinner_StateChanged
      acquisitionSettingsChanged();
      //update any grids/surface shown
      for (int i = 0; i < regionManager_.getNumberOfRegions(); i++) {
         regionManager_.drawRegionOverlay(regionManager_.getRegion(i));
      }

      for (int i = 0; i < surfaceManager_.getNumberOfSurfaces(); i++) {
         surfaceManager_.drawSurfaceOverlay(surfaceManager_.getSurface(i));
      }
   }//GEN-LAST:event_acqOverlapPercentSpinner_StateChanged

   private void zStepSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_zStepSpinner_StateChanged
      acquisitionSettingsChanged();
   }//GEN-LAST:event_zStepSpinner_StateChanged

   private void collectionPlaneCombo_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_collectionPlaneCombo_ActionPerformed
      acquisitionSettingsChanged();
   }//GEN-LAST:event_collectionPlaneCombo_ActionPerformed

   private void footprint2DComboBox_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_footprint2DComboBox_ActionPerformed
      acquisitionSettingsChanged();
   }//GEN-LAST:event_footprint2DComboBox_ActionPerformed

   private void withinDistanceFromFootprintCombo_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_withinDistanceFromFootprintCombo_ActionPerformed
      acquisitionSettingsChanged();
   }//GEN-LAST:event_withinDistanceFromFootprintCombo_ActionPerformed

   private void fixedDistanceSurfaceComboBox_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_fixedDistanceSurfaceComboBox_ActionPerformed
      acquisitionSettingsChanged();
   }//GEN-LAST:event_fixedDistanceSurfaceComboBox_ActionPerformed

   private void distanceAboveFixedSurfaceSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_distanceAboveFixedSurfaceSpinner_StateChanged
      acquisitionSettingsChanged();
   }//GEN-LAST:event_distanceAboveFixedSurfaceSpinner_StateChanged

   private void distanceBelowFixedSurfaceSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_distanceBelowFixedSurfaceSpinner_StateChanged
      acquisitionSettingsChanged();
   }//GEN-LAST:event_distanceBelowFixedSurfaceSpinner_StateChanged

   private void umBelowBottomSurfaceSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_umBelowBottomSurfaceSpinner_StateChanged
      acquisitionSettingsChanged();
   }//GEN-LAST:event_umBelowBottomSurfaceSpinner_StateChanged

   private void umAboveTopSurfaceSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_umAboveTopSurfaceSpinner_StateChanged
      acquisitionSettingsChanged();
   }//GEN-LAST:event_umAboveTopSurfaceSpinner_StateChanged

   private void volumeBetweenFootprintCombo_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_volumeBetweenFootprintCombo_ActionPerformed
      acquisitionSettingsChanged();
   }//GEN-LAST:event_volumeBetweenFootprintCombo_ActionPerformed

   private void bottomSurfaceCombo_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_bottomSurfaceCombo_ActionPerformed
      acquisitionSettingsChanged();
   }//GEN-LAST:event_bottomSurfaceCombo_ActionPerformed

   private void topSurfaceCombo_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_topSurfaceCombo_ActionPerformed
      acquisitionSettingsChanged();
   }//GEN-LAST:event_topSurfaceCombo_ActionPerformed

   private void zEndSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_zEndSpinner_StateChanged
      acquisitionSettingsChanged();
   }//GEN-LAST:event_zEndSpinner_StateChanged

   private void zStartSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_zStartSpinner_StateChanged
      acquisitionSettingsChanged();
   }//GEN-LAST:event_zStartSpinner_StateChanged

   private void simpleZStackFootprintCombo_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_simpleZStackFootprintCombo_ActionPerformed
      acquisitionSettingsChanged();
   }//GEN-LAST:event_simpleZStackFootprintCombo_ActionPerformed

   private void timePointsCheckBox_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_timePointsCheckBox_ActionPerformed
      for (Component c : timePointsPanel_.getComponents()) {
         c.setEnabled(timePointsCheckBox_.isSelected());
      }
      acquisitionSettingsChanged();
   }//GEN-LAST:event_timePointsCheckBox_ActionPerformed

   private void timeIntervalSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_timeIntervalSpinner_StateChanged
      acquisitionSettingsChanged();
   }//GEN-LAST:event_timeIntervalSpinner_StateChanged

   private void numTimePointsSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_numTimePointsSpinner_StateChanged
      acquisitionSettingsChanged();
   }//GEN-LAST:event_numTimePointsSpinner_StateChanged

   private void timeIntevalUnitCombo_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_timeIntevalUnitCombo_ActionPerformed
      acquisitionSettingsChanged();
   }//GEN-LAST:event_timeIntevalUnitCombo_ActionPerformed

   private void loadButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_loadButton_ActionPerformed
      regionManager_.loadRegions(this);
   }//GEN-LAST:event_loadButton_ActionPerformed

   private void saveButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_saveButton_ActionPerformed
      regionManager_.saveRegions(this);
   }//GEN-LAST:event_saveButton_ActionPerformed

   private void deleteAllRegionsButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_deleteAllRegionsButton_ActionPerformed
      regionManager_.deleteAll();
   }//GEN-LAST:event_deleteAllRegionsButton_ActionPerformed

   private void deleteSelectedRegionButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_deleteSelectedRegionButton_ActionPerformed
      if (gridTable_.getSelectedRow() != -1) {
         regionManager_.delete(gridTable_.getSelectedRow());
      }
   }//GEN-LAST:event_deleteSelectedRegionButton_ActionPerformed

   private void jButton2ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_jButton2ActionPerformed
      // TODO add your handling code here:
   }//GEN-LAST:event_jButton2ActionPerformed

   private void jButton3ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_jButton3ActionPerformed
      // TODO add your handling code here:
   }//GEN-LAST:event_jButton3ActionPerformed

   private void noCollectionPlaneButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_noCollectionPlaneButton_ActionPerformed
      // TODO add your handling code here:
   }//GEN-LAST:event_noCollectionPlaneButton_ActionPerformed

   // Variables declaration - do not modify//GEN-BEGIN:variables
   private javax.swing.JComboBox ChannelGroupCombo_;
   private javax.swing.JPanel ChannelsTab_;
   private javax.swing.JTabbedPane acq2D3DTabbedPane_;
   private javax.swing.JPanel acq2DPanel_;
   private javax.swing.JPanel acq3DPanel_;
   private javax.swing.JComboBox acqOrderCombo_;
   private javax.swing.JLabel acqOrderLabel_;
   private javax.swing.JSpinner acqOverlapPercentSpinner_;
   private javax.swing.JPanel acqPanel;
   private javax.swing.JTabbedPane acqTabbedPane_;
   private javax.swing.JLabel acqTileOverlapLabel_;
   private javax.swing.JButton addAcqButton_;
   private javax.swing.JPanel bottomPanel_;
   private javax.swing.JComboBox bottomSurfaceCombo_;
   private javax.swing.JLabel bottomSurfaceLabel_;
   private javax.swing.JButton calinrateTilingButton_;
   private javax.swing.JLabel channelGroupLabel_;
   private javax.swing.JTable channelsTable_;
   private javax.swing.JLabel citeLink_;
   private javax.swing.JComboBox collectionPlaneCombo_;
   private javax.swing.JLabel collectionPlaneLabel_;
   private javax.swing.JButton deleteAllRegionsButton_;
   private javax.swing.JButton deleteSelectedRegionButton_;
   private javax.swing.JSpinner distanceAboveFixedSurfaceSpinner_;
   private javax.swing.JLabel distanceAboveSurfaceLabel_;
   private javax.swing.JSpinner distanceBelowFixedSurfaceSpinner_;
   private javax.swing.JLabel distanceBelowSurfaceLabel_;
   private javax.swing.JLabel estDurationLabel_;
   private javax.swing.JTabbedPane exploreAcqTabbedPane_;
   private javax.swing.JButton exploreBrowseButton_;
   private javax.swing.JComboBox exploreChannelGroupCombo_;
   private javax.swing.ButtonGroup exploreFilterMethodButtonGroup_;
   private javax.swing.JLabel exploreOverlapLabel_;
   private javax.swing.JPanel explorePanel;
   private javax.swing.JLabel explorePercentLabel_;
   private javax.swing.JLabel exploreSavingDirLabel_;
   private javax.swing.JLabel exploreSavingNameLabel_;
   private javax.swing.JTextField exploreSavingNameTextField_;
   private javax.swing.JSpinner exploreTileOverlapSpinner_;
   private javax.swing.JLabel exploreZStepLabel_;
   private javax.swing.JSpinner exploreZStepSpinner_;
   private javax.swing.ButtonGroup filterMethodButtonGroup_;
   private javax.swing.JComboBox fixedDistanceSurfaceComboBox_;
   private javax.swing.JPanel fixedDistanceZPanel_;
   private javax.swing.JLabel fixedSurfaceLabel_;
   private javax.swing.JLabel footprin2DLabel_;
   private javax.swing.JComboBox footprint2DComboBox_;
   private javax.swing.JTextField globalSavingDirTextField_;
   private javax.swing.JTable gridTable_;
   private javax.swing.JButton helpButton_;
   private javax.swing.JButton jButton2;
   private javax.swing.JButton jButton3;
   private javax.swing.JLabel jLabel11;
   private javax.swing.JLabel jLabel12;
   private javax.swing.JLabel jLabel2;
   private javax.swing.JLabel jLabel3;
   private javax.swing.JLabel jLabel5;
   private javax.swing.JPanel jPanel1;
   private javax.swing.JPanel jPanel4;
   private javax.swing.JScrollPane jScrollPane1;
   private javax.swing.JScrollPane jScrollPane2;
   private javax.swing.JButton loadButton_;
   private javax.swing.JButton moveAcqDownButton_;
   private javax.swing.JButton moveAcqUpButton_;
   private javax.swing.JScrollPane multipleAcqScrollPane_;
   private javax.swing.JTable multipleAcqTable_;
   private javax.swing.JButton newExploreWindowButton_;
   private javax.swing.JRadioButton noCollectionPlaneButton_;
   private javax.swing.JLabel numTimePointsLabel_;
   private javax.swing.JSpinner numTimePointsSpinner_;
   private javax.swing.JButton openDatasetButton_;
   private javax.swing.JPanel panel2D_;
   private javax.swing.JButton removeAcqButton_;
   private javax.swing.JPanel root_panel_;
   private javax.swing.JButton runAcqButton_;
   private javax.swing.JButton saveButton_;
   private javax.swing.JPanel simpleZPanel_;
   private javax.swing.JComboBox simpleZStackFootprintCombo_;
   private javax.swing.JPanel spaceTab_;
   private javax.swing.JLabel surfacesAndGrdisLabel_;
   private javax.swing.JLabel tileOverlapPercentLabel_;
   private javax.swing.JLabel timeIntervalLabel_;
   private javax.swing.JSpinner timeIntervalSpinner_;
   private javax.swing.JComboBox timeIntevalUnitCombo_;
   private javax.swing.JCheckBox timePointsCheckBox_;
   private javax.swing.JPanel timePointsPanel_;
   private javax.swing.JPanel timePointsTab_;
   private javax.swing.JPanel topPanel_;
   private javax.swing.JComboBox topSurfaceCombo_;
   private javax.swing.JLabel topSurfaceLabel_;
   private javax.swing.JLabel umAboveLabel_;
   private javax.swing.JSpinner umAboveTopSurfaceSpinner_;
   private javax.swing.JLabel umAboveVolBetweenLabel_;
   private javax.swing.JSpinner umBelowBottomSurfaceSpinner_;
   private javax.swing.JLabel umBelowLabel_;
   private javax.swing.JLabel umBelowVolBetweenLabel_;
   private javax.swing.JRadioButton useCollectionPlaneButton_;
   private javax.swing.JLabel userGuideLink_;
   private javax.swing.JComboBox volumeBetweenFootprintCombo_;
   private javax.swing.JPanel volumeBetweenZPanel_;
   private javax.swing.JComboBox withinDistanceFromFootprintCombo_;
   private javax.swing.ButtonGroup z2DButtonGroup_;
   private javax.swing.JLabel zEndLabel;
   private javax.swing.JSpinner zEndSpinner_;
   private javax.swing.ButtonGroup zStackModeButtonGroup_;
   private javax.swing.JTabbedPane zStackTypeTabbedPane_;
   private javax.swing.JLabel zStartLabel;
   private javax.swing.JSpinner zStartSpinner_;
   private javax.swing.JLabel zStepLabel_;
   private javax.swing.JSpinner zStepSpinner_;
   // End of variables declaration//GEN-END:variables

}

