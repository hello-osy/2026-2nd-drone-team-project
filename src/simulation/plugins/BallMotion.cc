#include <chrono>
#include <cmath>
#include <atomic>
#include <gz/transport/Node.hh>
#include <gz/msgs/boolean.pb.h>
#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Model.hh>

// Scripted kinematic ball: simulation time, independent of rendering / CPU FPS.
class BallMotion : public gz::sim::System,
                   public gz::sim::ISystemConfigure,
                   public gz::sim::ISystemPreUpdate {
  gz::sim::Model model;
  gz::transport::Node node;
  std::atomic<bool> running{false};
  double elapsed = 0;
public:
  void Configure(const gz::sim::Entity &entity,
      const std::shared_ptr<const sdf::Element> &,
      gz::sim::EntityComponentManager &, gz::sim::EventManager &) override {
    model = gz::sim::Model(entity);
    node.Subscribe("/pd/ball/run", &BallMotion::Run, this);
  }
  void Run(const gz::msgs::Boolean &msg) { running = msg.data(); }
  void PreUpdate(const gz::sim::UpdateInfo &info,
      gz::sim::EntityComponentManager &ecm) override {
    if (info.paused) return;
    if (info.dt.count() < 0 || !running) elapsed = 0;
    else elapsed += std::chrono::duration<double>(info.dt).count();
    const double t = elapsed;
    model.SetWorldPoseCmd(ecm, gz::math::Pose3d(
        3.0 * std::sin(.08*t), 2.0 * std::sin(.16*t), .115,
        0, t*.8, 0));
  }
};
GZ_ADD_PLUGIN(BallMotion, gz::sim::System,
              BallMotion::ISystemConfigure, BallMotion::ISystemPreUpdate)
